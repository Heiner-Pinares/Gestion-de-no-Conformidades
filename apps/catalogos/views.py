"""Gobernanza, sin poderes de validación implícitos."""
import csv
from urllib.parse import urlencode
from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.forms.models import model_to_dict
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from apps.accounts.forms import UsuarioCreacionForm, UsuarioEdicionForm
from apps.accounts.models import Usuario
from apps.accounts.permissions import es_administrador, es_validador
from .forms import CATALOGOS, formulario_catalogo
from .models import AuditoriaAdministracion


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


@solo_admin
def usuarios(request):
    q = request.GET.get("q", "").strip()
    qs = Usuario.objects.filter(is_superuser=False).prefetch_related("groups").order_by("username")
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    return render(request, "administrador/usuarios.html", {"pagina": Paginator(qs, 25).get_page(request.GET.get("page")), "q": q, "filtros": urlencode({"q": q})})


@solo_admin
def usuario_crear(request):
    form = UsuarioCreacionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            obj = form.save()
            obj.groups.set(form.cleaned_data["roles"])
            registrar_auditoria(request.user, "Usuario", obj.pk, "crear", {}, {"username": obj.username, "roles": list(obj.groups.values_list("name", flat=True))})
        messages.success(request, "Usuario creado con sus roles.")
        return redirect("usuarios")
    return render(request, "administrador/formulario.html", {"form": form, "titulo": "Crear usuario", "volver": "usuarios"})


@solo_admin
def usuario_editar(request, pk):
    obj = get_object_or_404(Usuario, pk=pk, is_superuser=False)
    form = UsuarioEdicionForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Serializa cambios de roles: evita retirar simultáneamente al último administrador.
            Group.objects.select_for_update().get(name="ADMINISTRADOR")
            actual = Usuario.objects.select_for_update().get(pk=pk)
            roles = list(form.cleaned_data["roles"])
            conserva_admin = form.cleaned_data["is_active"] and any(r.name == "ADMINISTRADOR" for r in roles)
            otros_admin = Usuario.objects.filter(is_active=True, groups__name="ADMINISTRADOR").exclude(pk=pk).exists()
            if actual.groups.filter(name="ADMINISTRADOR").exists() and not conserva_admin and not otros_admin:
                form.add_error(None, "Debe permanecer al menos un administrador activo.")
            else:
                antes = serializar(actual, ["first_name", "last_name", "email", "area", "cargo", "is_active"])
                antes["roles"] = list(actual.groups.values_list("name", flat=True))
                guardado = form.save()
                guardado.groups.set(roles)
                despues = serializar(guardado, ["first_name", "last_name", "email", "area", "cargo", "is_active"])
                despues["roles"] = [r.name for r in roles]
                registrar_auditoria(request.user, "Usuario", pk, "actualizar", antes, despues)
                messages.success(request, "Usuario actualizado.")
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
    tipo = request.GET.get("tipo", "procesos")
    if tipo not in CATALOGOS:
        raise Http404
    modelo, _, titulo = CATALOGOS[tipo]
    qs = modelo.objects.all()
    if tipo == "matriz":
        qs = qs.select_related("impacto", "urgencia", "prioridad")
    return render(request, "administrador/catalogos.html", {
        "tipos": [(k, v[2]) for k, v in CATALOGOS.items()], "tipo": tipo, "titulo": titulo,
        "pagina": Paginator(qs, 30).get_page(request.GET.get("page")),
        "filtros": urlencode({"tipo": tipo}),
        "puede_crear": tipo not in ("tipos", "impactos", "urgencias", "categorias"),
    })


@solo_admin
def catalogo_editar(request, tipo, pk=None):
    if tipo not in CATALOGOS:
        raise Http404
    modelo, campos, titulo = CATALOGOS[tipo]
    if pk is None and tipo in ("tipos", "impactos", "urgencias", "categorias"):
        raise PermissionDenied
    obj = get_object_or_404(modelo, pk=pk) if pk is not None else None
    form = formulario_catalogo(tipo, request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            anterior = modelo.objects.select_for_update().get(pk=pk) if obj else None
            antes = serializar(anterior, campos) if anterior else {}
            guardado = form.save()
            registrar_auditoria(request.user, modelo.__name__, guardado.pk, "actualizar" if anterior else "crear", antes, serializar(guardado, campos))
        messages.success(request, "Catálogo guardado. Los valores históricos del caso se conservan.")
        return redirect(f"/administracion/catalogos/?tipo={tipo}")
    return render(request, "administrador/formulario.html", {"form": form, "titulo": titulo, "volver": "catalogos"})


@solo_admin
def auditoria(request):
    qs = AuditoriaAdministracion.objects.select_related("usuario")
    return render(request, "administrador/auditoria.html", {"pagina": Paginator(qs, 30).get_page(request.GET.get("page"))})


@login_required
def reportes(request):
    from apps.hallazgos.selectors import hallazgos_visibles
    from apps.hallazgos.models import EvaluacionEficacia
    if not (es_administrador(request.user) or es_validador(request.user)):
        raise PermissionDenied
    qs = hallazgos_visibles(request.user)
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
    total = qs.count()
    evaluaciones = EvaluacionEficacia.objects.filter(ciclo__hallazgo__in=qs)
    numero_evaluaciones = evaluaciones.count()
    resumen = {
        "Total": total, "Abiertos": qs.exclude(estado__in=["CERRADO", "CANCELADO"]).count(),
        "Críticos": qs.filter(es_critica="SI").count(),
        "Vencidos": qs.exclude(estado__in=["CERRADO", "CANCELADO"]).filter(fecha_solucion__lt=timezone.localdate()).count(),
        "En verificación": qs.filter(estado="EN_VERIFICACION").count(),
        "Cerrados": qs.filter(estado="CERRADO").count(),
    }
    eficacia = round(100 * evaluaciones.filter(resultado="EFICAZ").count() / numero_evaluaciones, 1) if numero_evaluaciones else None
    from apps.hallazgos.estados import ESTADOS
    estados = [{"estado__nombre": dict(ESTADOS).get(row["estado"], row["estado"]), "total": row["total"]} for row in qs.order_by().values("estado").annotate(total=Count("pk")).order_by("estado")]
    return render(request, "administrador/reportes.html", {"resumen": resumen, "eficacia": eficacia, "n_evaluaciones": numero_evaluaciones, "estados": estados})
