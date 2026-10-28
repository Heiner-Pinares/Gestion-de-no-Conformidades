"""Gobernanza, sin poderes de validación implícitos."""
import csv
from urllib.parse import urlencode
from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Case, CharField, Count, F, Q, When
from django.db.models.functions import ExtractMonth
from django.forms.models import model_to_dict
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from apps.accounts.forms import UsuarioCreacionForm, UsuarioEdicionForm
from apps.accounts.models import Usuario, UsuarioRol
from apps.accounts.permissions import es_administrador, es_validador
from .forms import (
    CATALOGOS, ConfiguracionImpactoForm, ConfiguracionUrgenciaForm,
    CorreoCompromisoCatalogoForm, formulario_catalogo,
)
from .models import (
    AuditoriaAdministracion, Catalogo, ConfiguracionImpacto, ConfiguracionUrgencia,
    Proceso, ProcesoValidador, Subproceso,
)
from .services import (
    TIPO_COPIA, TIPO_PARA, correos_queryset, detalle_actividad,
    guardar_correo, tipo_correo, actividades_queryset,
)


TIPO_ACTIVIDADES = "actividades"
TITULO_ACTIVIDADES = "Actividades"
ALCANCE_INDICADORES_PREDETERMINADO = (
    "Facturación",
    "Post-Facturación",
    "Control y Mejoras",
)


def tipos_catalogo():
    return [(k, v[2]) for k, v in CATALOGOS.items()] + [(TIPO_ACTIVIDADES, TITULO_ACTIVIDADES)]


def datos_actividad(actividad):
    detalle = detalle_actividad(actividad)
    return {
        "proceso": str(detalle["proceso"].pk) if detalle["proceso"] else "",
        "subproceso": str(detalle["subproceso"].pk) if detalle["subproceso"] else "",
        "nombre": actividad.nombre,
        "activo": str(actividad.activo),
    }


def solo_admin(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not es_administrador(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def serializar(obj, fields):
    datos = model_to_dict(obj, fields=fields)
    return {k: [str(item.pk) for item in v] if isinstance(v, list) else str(v) for k, v in datos.items()}


def registrar_auditoria(usuario, entidad, objeto, accion, antes, despues):
    AuditoriaAdministracion.objects.create(usuario=usuario, entidad=entidad, objeto=str(objeto), accion=accion, antes=antes, despues=despues)


def guardar_procesos_validador(usuario, procesos):
    """Sincroniza la relación normalizada y el JSON compatible del proceso."""
    seleccionados = {proceso.pk for proceso in procesos}
    anteriores = set(
        ProcesoValidador.objects.filter(usuario=usuario).values_list(
            "proceso_id", flat=True,
        )
    )
    for proceso in Proceso.objects.select_for_update().filter(
        pk__in=anteriores | seleccionados,
    ):
        validadores = set(proceso.validadores_ids or [])
        if proceso.pk in seleccionados:
            validadores.add(usuario.pk)
        else:
            validadores.discard(usuario.pk)
        proceso.validadores_ids = sorted(validadores)
        proceso.save(update_fields=["validadores_ids"])


@solo_admin
def usuarios(request):
    q = request.GET.get("q", "").strip()
    rol = request.GET.get("rol", "").strip()
    qs = Usuario.objects.filter(is_superuser=False).select_related("jefe").prefetch_related(
        "asignaciones_proceso__proceso",
    ).order_by("username")
    if q:
        qs = qs.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q)
            | Q(last_name__icontains=q) | Q(email__icontains=q)
            | Q(cargo__icontains=q) | Q(area__icontains=q)
            | Q(gerencia__icontains=q) | Q(direccion__icontains=q)
            | Q(jefe__first_name__icontains=q) | Q(jefe__last_name__icontains=q)
        )
    if rol:
        usuarios_del_rol = UsuarioRol.objects.filter(rol=rol).values("usuario_id")
        qs = qs.filter(pk__in=usuarios_del_rol)
    filtros = {"q": q, "rol": rol}
    return render(request, "administrador/usuarios.html", {
        "pagina": Paginator(qs, 10).get_page(request.GET.get("page")),
        "q": q,
        "rol": rol,
        "roles": ["USUARIO", "VALIDADOR", "ADMINISTRADOR"],
        "total_usuarios": Usuario.objects.filter(is_superuser=False).count(),
        "filtros": urlencode({k: v for k, v in filtros.items() if v}),
    })


@solo_admin
def usuario_crear(request):
    form = UsuarioCreacionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            obj = form.save()
            obj.set_roles(form.cleaned_data["roles"])
            procesos = form.cleaned_data["procesos_validacion"]
            guardar_procesos_validador(obj, procesos)
            registrar_auditoria(request.user, "Usuario", obj.pk, "crear", {}, {
                "username": obj.username,
                "roles": obj.roles,
                "procesos_validacion": [proceso.pk for proceso in procesos],
            })
        messages.success(request, "Usuario creado con sus roles y procesos de validación.")
        return redirect("usuarios")
    return render(request, "administrador/formulario.html", {"form": form, "titulo": "Crear usuario", "volver": "usuarios"})


@solo_admin
def usuario_editar(request, pk):
    obj = get_object_or_404(Usuario, pk=pk, is_superuser=False)
    form = UsuarioEdicionForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Serializa cambios de roles: evita retirar simultáneamente al último administrador.
            actual = Usuario.objects.select_for_update().get(pk=pk)
            roles = list(form.cleaned_data["roles"])
            conserva_admin = form.cleaned_data["is_active"] and "ADMINISTRADOR" in roles
            otros_admin = Usuario.objects.filter(
                is_active=True,
                asignaciones_rol__rol="ADMINISTRADOR",
            ).exclude(pk=pk).exists()
            if actual.has_role("ADMINISTRADOR") and not conserva_admin and not otros_admin:
                form.add_error(None, "Debe permanecer al menos un administrador activo.")
            else:
                antes = serializar(actual, ["first_name", "last_name", "email", "area", "gerencia", "direccion", "cargo", "jefe", "is_active"])
                antes["roles"] = actual.roles
                antes["procesos_validacion"] = list(
                    ProcesoValidador.objects.filter(usuario=actual).values_list(
                        "proceso_id", flat=True,
                    )
                )
                guardado = form.save()
                guardado.set_roles(roles)
                procesos = form.cleaned_data["procesos_validacion"]
                guardar_procesos_validador(guardado, procesos)
                despues = serializar(guardado, ["first_name", "last_name", "email", "area", "gerencia", "direccion", "cargo", "jefe", "is_active"])
                despues["roles"] = roles
                despues["procesos_validacion"] = [proceso.pk for proceso in procesos]
                registrar_auditoria(request.user, "Usuario", pk, "actualizar", antes, despues)
                messages.success(request, "Usuario y procesos de validación actualizados.")
                return redirect("usuarios")
    return render(request, "administrador/formulario.html", {"form": form, "titulo": f"Editar {obj.username}", "volver": "usuarios", "usuario_editado": obj})


@solo_admin
def usuario_password(request, pk):
    obj = get_object_or_404(Usuario, pk=pk, is_superuser=False)
    form = SetPasswordForm(obj, request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            form.save()
            registrar_auditoria(request.user, "Usuario", pk, "cambiar_clave", {}, {})
        messages.success(request, "Contraseña actualizada. No se almacena en texto plano.")
        return redirect("usuarios")
    return render(request, "administrador/formulario.html", {"form": form, "titulo": f"Establecer contraseña de {obj.username}", "volver": "usuarios"})


@solo_admin
def catalogos(request):
    tipo = request.GET.get("tipo", "").strip()
    if not tipo:
        resumen_catalogos = [
            {"clave": clave, "titulo": titulo, "total": modelo.objects.count()}
            for clave, (modelo, _, titulo) in CATALOGOS.items()
        ]
        resumen_catalogos.append({
            "clave": TIPO_ACTIVIDADES,
            "titulo": TITULO_ACTIVIDADES,
            "total": actividades_queryset().count(),
        })
        return render(request, "administrador/catalogos.html", {
            "tipos": tipos_catalogo(),
            "resumen_catalogos": resumen_catalogos,
            "correos_total": correos_queryset().filter(activo=True).count(),
        })
    if tipo not in CATALOGOS and tipo != TIPO_ACTIVIDADES:
        raise Http404
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    if estado not in {"", "activo", "inactivo"}:
        estado = ""
    if tipo == TIPO_ACTIVIDADES:
        titulo = TITULO_ACTIVIDADES
        qs = actividades_queryset()
    else:
        modelo, _, titulo = CATALOGOS[tipo]
        qs = modelo.objects.all()
        if tipo == "matriz":
            qs = qs.select_related("impacto", "urgencia", "prioridad")
    if estado:
        qs = qs.filter(activo=estado == "activo")
    if q:
        campos = {campo.name for campo in qs.model._meta.fields}
        busqueda = Q()
        if "nombre" in campos:
            busqueda |= Q(nombre__icontains=q)
        if "codigo" in campos:
            busqueda |= Q(codigo__icontains=q)
        if "texto" in campos:
            busqueda |= Q(texto__icontains=q)
        if tipo == "subprocesos":
            busqueda |= Q(proceso__nombre__icontains=q)
        if busqueda:
            qs = qs.filter(busqueda)
    pagina = Paginator(qs, 10).get_page(request.GET.get("page"))
    if tipo == TIPO_ACTIVIDADES:
        for actividad in pagina.object_list:
            detalle = detalle_actividad(actividad)
            actividad.proceso_catalogo = detalle["proceso"]
            actividad.subproceso_catalogo = detalle["subproceso"]
    return render(request, "administrador/catalogos.html", {
        "tipos": tipos_catalogo(), "tipo": tipo, "titulo": titulo,
        "pagina": pagina, "q": q, "estado": estado,
        "filtros": urlencode({k: v for k, v in {"tipo": tipo, "q": q, "estado": estado}.items() if v}),
        "puede_crear": tipo not in ("tipos", "impactos", "urgencias", "categorias"),
    })


@solo_admin
def catalogos_correos(request):
    """Administra To/CC adicionales sin alterar responsable ni jefe."""
    form = CorreoCompromisoCatalogoForm(
        request.POST if request.method == "POST" and request.POST.get("accion") == "agregar" else None
    )
    if request.method == "POST":
        accion = request.POST.get("accion")
        if accion == "agregar" and form.is_valid():
            with transaction.atomic():
                registro, creado = guardar_correo(
                    tipo=form.cleaned_data["tipo"],
                    correo=form.cleaned_data["correo"],
                )
                registrar_auditoria(
                    request.user,
                    "CorreoCompromisoCatalogo",
                    registro.pk,
                    "crear" if creado else "reactivar",
                    {},
                    {
                        "tipo": tipo_correo(registro),
                        "correo": registro.nombre,
                        "activo": str(registro.activo),
                    },
                )
            messages.success(
                request,
                "Correo agregado." if creado else "El correo ya existía y quedó activo nuevamente.",
            )
            return redirect("catalogos_correos")
        if accion == "cambiar_estado":
            registro = get_object_or_404(correos_queryset(), pk=request.POST.get("registro_id"))
            activo = request.POST.get("activo") == "1"
            with transaction.atomic():
                actual = Catalogo.objects.select_for_update().get(pk=registro.pk)
                anterior = actual.activo
                actual.activo = activo
                actual.save(update_fields=["activo"])
                registrar_auditoria(
                    request.user,
                    "CorreoCompromisoCatalogo",
                    actual.pk,
                    "activar" if activo else "quitar",
                    {"activo": str(anterior)},
                    {
                        "tipo": tipo_correo(actual),
                        "correo": actual.nombre,
                        "activo": str(actual.activo),
                    },
                )
            messages.success(
                request,
                "Correo habilitado nuevamente." if activo else "Correo quitado de los próximos envíos.",
            )
            return redirect("catalogos_correos")

    return render(request, "administrador/correos_compromisos.html", {
        "form": form,
        "correos_para": correos_queryset(TIPO_PARA).order_by("-activo", "nombre"),
        "correos_copia": correos_queryset(TIPO_COPIA).order_by("-activo", "nombre"),
    })


@solo_admin
def catalogo_editar(request, tipo, pk=None):
    if tipo not in CATALOGOS and tipo != TIPO_ACTIVIDADES:
        raise Http404
    if tipo == TIPO_ACTIVIDADES:
        modelo, campos, titulo = Catalogo, ["proceso", "subproceso", "nombre", "activo"], TITULO_ACTIVIDADES
    else:
        modelo, campos, titulo = CATALOGOS[tipo]
    if pk is None and tipo in ("tipos", "impactos", "urgencias", "categorias"):
        raise PermissionDenied
    if tipo == TIPO_ACTIVIDADES:
        obj = get_object_or_404(actividades_queryset(), pk=pk) if pk is not None else None
    else:
        obj = get_object_or_404(modelo, pk=pk) if pk is not None else None
    form = formulario_catalogo(tipo, request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            if tipo == TIPO_ACTIVIDADES:
                anterior = actividades_queryset().select_for_update().get(pk=pk) if obj else None
                antes = datos_actividad(anterior) if anterior else {}
                form.instance = anterior
            else:
                anterior = modelo.objects.select_for_update().get(pk=pk) if obj else None
                antes = serializar(anterior, campos) if anterior else {}
            guardado = form.save()
            if "validadores" in form.cleaned_data:
                guardado.validadores.set(form.cleaned_data["validadores"])
            despues = datos_actividad(guardado) if tipo == TIPO_ACTIVIDADES else serializar(guardado, campos)
            if "validadores" in form.cleaned_data:
                despues["validadores"] = list(guardado.validadores.values_list("pk", flat=True))
            entidad = "ActividadCatalogo" if tipo == TIPO_ACTIVIDADES else modelo.__name__
            registrar_auditoria(request.user, entidad, guardado.pk, "actualizar" if anterior else "crear", antes, despues)
        messages.success(request, "Catálogo guardado. Los valores históricos del caso se conservan.")
        return redirect(f"/administracion/catalogos/?tipo={tipo}")
    return render(request, "administrador/formulario.html", {"form": form, "titulo": titulo, "volver": "catalogos"})


@solo_admin
@require_POST
def catalogo_eliminar(request, tipo, pk):
    """Elimina un valor inactivo únicamente cuando no tiene referencias históricas."""
    if tipo not in CATALOGOS and tipo != TIPO_ACTIVIDADES:
        raise Http404

    if tipo == TIPO_ACTIVIDADES:
        modelo, campos = Catalogo, ["proceso", "subproceso", "nombre", "activo"]
        objeto = get_object_or_404(actividades_queryset(), pk=pk)
        entidad = "ActividadCatalogo"
    else:
        modelo, campos, _ = CATALOGOS[tipo]
        objeto = get_object_or_404(modelo, pk=pk)
        entidad = modelo.__name__

    nombre = str(objeto)
    destino = f"/administracion/catalogos/?tipo={tipo}"
    eliminados = {}
    try:
        with transaction.atomic():
            if tipo == TIPO_ACTIVIDADES:
                actual = actividades_queryset().select_for_update().get(pk=objeto.pk)
                antes = datos_actividad(actual)
            else:
                actual = modelo.objects.select_for_update().get(pk=objeto.pk)
                antes = serializar(actual, campos)
            if actual.activo:
                raise ValidationError(
                    "Primero marque el registro como inactivo desde Editar y luego elimínelo."
                )
            if tipo in {"procesos", "subprocesos"}:
                from apps.hallazgos.models import Hallazgo

                filtro_hallazgos = (
                    Q(proceso_id=actual.pk) | Q(subproceso__proceso_id=actual.pk)
                    if tipo == "procesos"
                    else Q(subproceso_id=actual.pk)
                )
                total_hallazgos = Hallazgo.objects.filter(filtro_hallazgos).count()
                if total_hallazgos:
                    etiqueta = "hallazgo" if total_hallazgos == 1 else "hallazgos"
                    raise ValidationError(
                        f'No se puede eliminar "{nombre}": {total_hallazgos} '
                        f"{etiqueta} lo utiliza. Manténgalo inactivo para conservar el historial."
                    )

                subprocesos = (
                    list(
                        Subproceso.objects.select_for_update()
                        .filter(proceso_id=actual.pk)
                        .order_by("pk")
                    )
                    if tipo == "procesos"
                    else [actual]
                )
                actividades_eliminadas = 0
                for subproceso in subprocesos:
                    cantidad, _ = actividades_queryset().filter(
                        codigo__startswith=f"ACT_{subproceso.pk}_",
                    ).delete()
                    actividades_eliminadas += cantidad
                if tipo == "procesos" and subprocesos:
                    Subproceso.objects.filter(
                        pk__in=[subproceso.pk for subproceso in subprocesos],
                    ).delete()
                eliminados = {
                    "subprocesos_eliminados": len(subprocesos) if tipo == "procesos" else 0,
                    "actividades_eliminadas": actividades_eliminadas,
                }
            identificador = actual.pk
            actual.delete()
            registrar_auditoria(
                request.user, entidad, identificador, "eliminar", antes, eliminados,
            )
    except ProtectedError:
        messages.error(
            request,
            f'No se puede eliminar "{nombre}" porque está relacionado con hallazgos '
            "u otros datos históricos. Manténgalo inactivo para que no aparezca en nuevos registros.",
        )
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        relacionados = []
        if eliminados.get("subprocesos_eliminados"):
            cantidad = eliminados["subprocesos_eliminados"]
            relacionados.append(
                f"{cantidad} {'subproceso' if cantidad == 1 else 'subprocesos'}"
            )
        if eliminados.get("actividades_eliminadas"):
            cantidad = eliminados["actividades_eliminadas"]
            relacionados.append(
                f"{cantidad} {'actividad' if cantidad == 1 else 'actividades'}"
            )
        detalle = f" junto con {' y '.join(relacionados)}" if relacionados else ""
        messages.success(request, f'"{nombre}" fue eliminado del catálogo{detalle}.')
    return redirect(destino)


@solo_admin
def configuracion_impacto(request):
    configuracion = ConfiguracionImpacto.objects.first()
    if configuracion is None:
        configuracion = ConfiguracionImpacto.objects.create()
    form = ConfiguracionImpactoForm(request.POST or None, instance=configuracion)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            actual = ConfiguracionImpacto.objects.select_for_update().get(pk=configuracion.pk)
            campos = list(form.fields)
            antes = serializar(actual, campos)
            guardado = form.save()
            registrar_auditoria(request.user, "ConfiguracionImpacto", guardado.pk, "actualizar", antes, serializar(guardado, campos))
        messages.success(request, "Los rangos de evaluación de impacto fueron actualizados.")
        return redirect("configuracion_impacto")
    return render(request, "administrador/impacto_configuracion.html", {"form": form, "configuracion": configuracion})


@solo_admin
def configuracion_urgencia(request):
    definiciones = {"FACTURACION": "Emisión de facturación", "POST_FACTURACION": "Vencimiento de ciclo"}
    configuraciones = {}
    for codigo, nombre in definiciones.items():
        configuraciones[codigo], _ = ConfiguracionUrgencia.objects.get_or_create(
            codigo=codigo, defaults={"nombre": nombre, "activo": True}
        )
    formularios = {
        codigo: ConfiguracionUrgenciaForm(request.POST or None, instance=obj, prefix=codigo.lower())
        for codigo, obj in configuraciones.items()
    }
    if request.method == "POST" and all(form.is_valid() for form in formularios.values()):
        with transaction.atomic():
            for codigo, form in formularios.items():
                actual = ConfiguracionUrgencia.objects.select_for_update().get(pk=configuraciones[codigo].pk)
                campos = list(form.fields)
                antes = serializar(actual, campos)
                guardado = form.save()
                registrar_auditoria(request.user, "ConfiguracionUrgencia", guardado.pk, "actualizar", antes, serializar(guardado, campos))
        messages.success(request, "Los rangos de evaluación de urgencia fueron actualizados.")
        return redirect("configuracion_urgencia")
    filas = [
        {"codigo": codigo, "titulo": definiciones[codigo], "area": configuraciones[codigo].get_codigo_display(), "form": formularios[codigo]}
        for codigo in definiciones
    ]
    return render(request, "administrador/urgencia_configuracion.html", {"filas": filas})


@solo_admin
def auditoria(request):
    qs = AuditoriaAdministracion.objects.select_related("usuario")
    return render(request, "administrador/auditoria.html", {"pagina": Paginator(qs, 30).get_page(request.GET.get("page"))})


@login_required
def reportes(request):
    from apps.hallazgos.selectors import hallazgos_visibles
    from apps.hallazgos.models import Accion
    if not (es_administrador(request.user) or es_validador(request.user)):
        raise PermissionDenied

    categorias_hallazgo = [
        ("pendiente", "Pendiente", {"BORRADOR", "PENDIENTE_VALIDACION", "DEVUELTO", "VALIDADO"}),
        ("en_proceso", "En proceso", {"ACCION_INMEDIATA", "EN_ANALISIS", "PBI_EN_GESTION", "PLAN_ACCION", "EN_IMPLEMENTACION", "EN_VERIFICACION", "REABIERTO"}),
        ("terminado", "Terminado", {"CERRADO"}),
        ("cancelado", "Cancelado", {"CANCELADO"}),
    ]
    categorias_actividad = [
        ("pendiente", "Pendiente", {"PENDIENTE"}),
        ("en_proceso", "En proceso", {"EN_PROCESO"}),
        ("terminado", "Terminado", {"COMPLETADA"}),
        ("cancelado", "Cancelado", {"CANCELADA"}),
    ]

    def con_jefatura(consulta, prefijo="proceso__"):
        """Usa la gerencia configurada y, si está vacía, el nombre real del proceso."""
        campo_gerencia = f"{prefijo}gerencia"
        campo_nombre = f"{prefijo}nombre"
        return consulta.annotate(jefatura_indicador=Case(
            When(**{campo_gerencia: ""}, then=F(campo_nombre)),
            When(**{f"{campo_gerencia}__isnull": True}, then=F(campo_nombre)),
            default=F(campo_gerencia),
            output_field=CharField(),
        ))

    def contar_estados(consulta, categorias):
        agregados = consulta.aggregate(**{
            clave: Count("pk", filter=Q(estado__in=estados), distinct=True)
            for clave, _etiqueta, estados in categorias
        })
        return {clave: agregados.get(clave, 0) or 0 for clave, _etiqueta, _estados in categorias}

    def agrupar_por_jefatura(consulta, categorias, grupos_iniciales=()):
        filas = consulta.order_by().values("jefatura_indicador", "estado").annotate(total=Count("pk", distinct=True))
        grupos = {
            nombre: {clave: 0 for clave, _etiqueta, _estados in categorias}
            for nombre in grupos_iniciales
        }
        for fila in filas:
            nombre = fila["jefatura_indicador"] or "Sin jefatura configurada"
            grupo = grupos.setdefault(nombre, {clave: 0 for clave, _etiqueta, _estados in categorias})
            for clave, _etiqueta, estados in categorias:
                if fila["estado"] in estados:
                    grupo[clave] += fila["total"]
                    break
        maximo = max((valor for grupo in grupos.values() for valor in grupo.values()), default=1) or 1
        nombres_ordenados = list(grupos_iniciales) + sorted(
            nombre for nombre in grupos if nombre not in grupos_iniciales
        )
        resultado = []
        for nombre in nombres_ordenados:
            valores = grupos[nombre]
            resultado.append({
                "nombre": nombre,
                "series": [
                    {"clave": clave, "etiqueta": etiqueta, "total": valores[clave],
                     "porcentaje": round(100 * valores[clave] / maximo)}
                    for clave, etiqueta, _estados in categorias
                ],
            })
        return resultado, maximo

    hallazgos_base = hallazgos_visibles(request.user).order_by()
    base = con_jefatura(hallazgos_base)
    jefaturas_registradas = base.order_by("jefatura_indicador").values_list(
        "jefatura_indicador", flat=True,
    ).distinct()
    jefaturas = list(dict.fromkeys([
        *ALCANCE_INDICADORES_PREDETERMINADO,
        *(valor for valor in jefaturas_registradas if valor),
    ]))
    jefatura = request.GET.get("jefatura", "").strip()
    if jefatura not in jefaturas:
        jefatura = ""

    if jefatura:
        alcance = base.filter(jefatura_indicador=jefatura)
        grupos_iniciales = ()
    else:
        alcance = base.filter(jefatura_indicador__in=ALCANCE_INDICADORES_PREDETERMINADO)
        grupos_iniciales = ALCANCE_INDICADORES_PREDETERMINADO

    anios = [fecha.year for fecha in alcance.dates("fecha_registro", "year", order="DESC")]
    if not anios:
        anios = [timezone.localdate().year]
    try:
        anio = int(request.GET.get("anio", anios[0]))
    except (TypeError, ValueError):
        anio = anios[0]
    if anio not in anios:
        anio = anios[0]

    qs = alcance.filter(fecha_registro__year=anio)

    if request.GET.get("formato") == "csv":
        respuesta = HttpResponse(content_type="text/csv; charset=utf-8")
        respuesta["Content-Disposition"] = 'attachment; filename="hallazgos.csv"'
        respuesta.write("\ufeff")
        writer = csv.writer(respuesta)
        writer.writerow(["Código", "Título", "Tipo", "Proceso", "Estado", "Responsable", "Fecha registro", "Fecha solución", "Prioridad", "Crítica"])
        def texto_seguro(valor):
            texto = str(valor or "")
            return "'" + texto if texto.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else texto
        for h in qs.iterator(chunk_size=500):
            writer.writerow([texto_seguro(v) for v in [h.codigo, h.titulo, h.tipo_registro, h.proceso, h.get_estado_display(), h.responsable, timezone.localtime(h.fecha_registro).isoformat(), h.fecha_solucion, h.prioridad_snapshot, h.get_es_critica_display()]])
        return respuesta
    conteo_hallazgos = contar_estados(qs, categorias_hallazgo)
    total_hallazgos = sum(conteo_hallazgos.values())
    hallazgos_cerrados = conteo_hallazgos["terminado"]
    tasa_cierre_hallazgos = round(100 * hallazgos_cerrados / total_hallazgos) if total_hallazgos else 0

    filas_mes = qs.annotate(mes_indicador=ExtractMonth("fecha_registro")).order_by().values(
        "mes_indicador", "estado",
    ).annotate(total=Count("pk", distinct=True))
    datos_mensuales = {mes: {clave: 0 for clave, _etiqueta, _estados in categorias_hallazgo} for mes in range(1, 13)}
    for fila in filas_mes:
        for clave, _etiqueta, estados in categorias_hallazgo:
            if fila["estado"] in estados:
                datos_mensuales[fila["mes_indicador"]][clave] += fila["total"]
                break
    maximo_mensual = max((sum(valores.values()) for valores in datos_mensuales.values()), default=1) or 1
    meses = []
    nombres_meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    for numero, etiqueta in enumerate(nombres_meses, 1):
        valores = datos_mensuales[numero]
        meses.append({
            "etiqueta": etiqueta,
            "total": sum(valores.values()),
            "series": [
                {"clave": clave, "total": valores[clave], "porcentaje": round(100 * valores[clave] / maximo_mensual)}
                for clave, _nombre, _estados in categorias_hallazgo
            ],
        })

    hallazgos_por_jefatura, maximo_hallazgos_jefatura = agrupar_por_jefatura(
        qs, categorias_hallazgo, grupos_iniciales,
    )

    acciones = Accion.objects.filter(ciclo__hallazgo__in=qs.values("pk")).order_by()
    conteo_acciones = contar_estados(acciones, categorias_actividad)
    total_acciones = sum(conteo_acciones.values())
    acciones_cerradas = conteo_acciones["terminado"]
    tasa_cierre_acciones = round(100 * acciones_cerradas / total_acciones) if total_acciones else 0
    maximo_estado_accion = max(conteo_acciones.values(), default=1) or 1
    estados_acciones = [
        {"clave": clave, "etiqueta": etiqueta, "total": conteo_acciones[clave],
         "porcentaje": round(100 * conteo_acciones[clave] / maximo_estado_accion)}
        for clave, etiqueta, _estados in categorias_actividad
    ]
    acciones_jefatura_qs = con_jefatura(acciones, "ciclo__hallazgo__proceso__")
    acciones_por_jefatura, maximo_acciones_jefatura = agrupar_por_jefatura(
        acciones_jefatura_qs, categorias_actividad, grupos_iniciales,
    )

    return render(request, "administrador/reportes.html", {
        "anios": anios, "anio": anio, "jefaturas": jefaturas, "jefatura": jefatura,
        "total_hallazgos": total_hallazgos,
        "hallazgos_cerrados": hallazgos_cerrados,
        "tasa_cierre_hallazgos": tasa_cierre_hallazgos,
        "angulo_cierre_hallazgos": round(180 * tasa_cierre_hallazgos / 100),
        "meses": meses, "maximo_mensual": maximo_mensual,
        "hallazgos_por_jefatura": hallazgos_por_jefatura,
        "maximo_hallazgos_jefatura": maximo_hallazgos_jefatura,
        "total_acciones": total_acciones,
        "acciones_cerradas": acciones_cerradas,
        "tasa_cierre_acciones": tasa_cierre_acciones,
        "angulo_cierre_acciones": round(180 * tasa_cierre_acciones / 100),
        "estados_acciones": estados_acciones,
        "acciones_por_jefatura": acciones_por_jefatura,
        "maximo_acciones_jefatura": maximo_acciones_jefatura,
    })
