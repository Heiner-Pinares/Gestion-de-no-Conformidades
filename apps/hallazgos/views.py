"""Adaptadores HTTP. Las reglas y transacciones pertenecen a services."""
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from apps.accounts.permissions import puede_gestionar, puede_validar, puede_ver
from apps.catalogos.models import CategoriaCausa
from .forms import (
    AccionForm, AnalisisCausaForm, BuscarHallazgoForm, ComunicacionForm,
    EvaluacionEficaciaForm, EvidenciaForm, HallazgoForm, PBIForm,
    ReprogramacionForm, SeguimientoForm, TransicionForm,
)
from .models import Accion, Evidencia, Hallazgo, Notificacion
from .selectors import acciones_disponibles, hallazgos_visibles, indicadores, timeline_hallazgo
from .services import (
    AccionService, CausaService, ComunicacionService, EficaciaService,
    EvidenciaService, HallazgoService, PBIService, WorkflowService,
)


def obtener_hallazgo(usuario, pk):
    return get_object_or_404(hallazgos_visibles(usuario), pk=pk)


def exigir_gestion(usuario, hallazgo):
    if not puede_gestionar(usuario, hallazgo):
        raise PermissionDenied


def errores(form, error):
    form.add_error(None, error.messages)


def redirigir_siguiente_paso(hallazgo):
    if hallazgo.estado == "EN_ANALISIS":
        return redirect("hallazgo_causa", pk=hallazgo.pk)
    if hallazgo.estado == "ACCION_INMEDIATA":
        return redirect("hallazgo_accion", pk=hallazgo.pk)
    return redirect("hallazgo_detalle", pk=hallazgo.pk)


def completar_formulario(request, form, titulo, operacion, hallazgo=None, **contexto):
    if request.method == "POST" and form.is_valid():
        try:
            operacion(form.cleaned_data)
        except ValidationError as error:
            errores(form, error)
        else:
            messages.success(request, "La información se guardó correctamente.")
            return redirect("hallazgo_detalle", pk=hallazgo.pk)
    return render(request, "hallazgos/formulario.html", {"form": form, "titulo": titulo, "hallazgo": hallazgo, **contexto})


@login_required
def inicio(request):
    qs = hallazgos_visibles(request.user)
    resumen = indicadores(request.user)
    resumen["en_proceso"] = qs.exclude(estado__in=["BORRADOR", "PENDIENTE_VALIDACION", "DEVUELTO", "CERRADO", "CANCELADO"]).count()
    return render(request, "hallazgos/inicio.html", {"recientes": qs[:6], "resumen": resumen})


def ayuda(request):
    return render(request, "ayuda.html")


@login_required
def hallazgo_crear(request):
    if not request.user.has_perm("accounts.registrar_hallazgo"):
        raise PermissionDenied
    form = HallazgoForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            hallazgo = HallazgoService.crear(usuario=request.user, datos=form.cleaned_data, borrador=request.POST.get("accion") != "continuar")
        except ValidationError as error:
            errores(form, error)
        else:
            if request.POST.get("accion") == "continuar":
                messages.success(request, f"{hallazgo.codigo} avanzó al siguiente paso.")
                return redirigir_siguiente_paso(hallazgo)
            messages.success(request, f"Borrador {hallazgo.codigo} guardado.")
            return redirect("hallazgo_detalle", pk=hallazgo.pk)
    return render(request, "hallazgos/registro.html", {"form": form, "titulo": "Registro de Solicitud de Acción Correctiva", "timeline": timeline_hallazgo(Hallazgo(estado="BORRADOR"))})


@login_required
def hallazgo_editar(request, pk):
    hallazgo = obtener_hallazgo(request.user, pk)
    autor = request.user.has_perm("accounts.registrar_hallazgo") and request.user.pk in [hallazgo.registrado_por_id, hallazgo.responsable_id]
    revisor = puede_validar(request.user, hallazgo) and hallazgo.estado == "PENDIENTE_VALIDACION"
    if not ((autor and hallazgo.estado in ["BORRADOR", "DEVUELTO"]) or revisor):
        raise PermissionDenied
    version = hallazgo.version
    form = HallazgoForm(request.POST or None, instance=hallazgo, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            version = forms.IntegerField(min_value=1).clean(request.POST.get("version"))
            with transaction.atomic():
                actualizado = HallazgoService.actualizar(usuario=request.user, hallazgo=hallazgo, datos=form.cleaned_data, version=version)
                if request.POST.get("accion") == "continuar":
                    actualizado = WorkflowService.continuar_identificacion(usuario=request.user, hallazgo=actualizado)
                hallazgo = actualizado
        except ValidationError as error:
            errores(form, error)
        else:
            messages.success(request, "Identificación actualizada con trazabilidad.")
            if request.POST.get("accion") == "continuar":
                return redirigir_siguiente_paso(hallazgo)
            return redirect("hallazgo_detalle", pk=pk)
    return render(request, "hallazgos/registro.html", {"form": form, "hallazgo": hallazgo, "version": version, "titulo": "Corregir identificación", "timeline": timeline_hallazgo(hallazgo)})


@login_required
def hallazgo_buscar(request):
    form = BuscarHallazgoForm(request.GET or None)
    qs = hallazgos_visibles(request.user)
    if request.GET and form.is_valid():
        datos = form.cleaned_data
        if datos.get("codigo"):
            qs = qs.filter(Q(codigo__icontains=datos["codigo"]) | Q(titulo__icontains=datos["codigo"]))
        for nombre in ("estado", "tipo_registro", "proceso"):
            if datos.get(nombre):
                qs = qs.filter(**{nombre: datos[nombre]})
        if datos.get("fecha_desde"):
            qs = qs.filter(fecha_registro__date__gte=datos["fecha_desde"])
        if datos.get("fecha_hasta"):
            qs = qs.filter(fecha_registro__date__lte=datos["fecha_hasta"])
    elif request.GET:
        qs = qs.none()
    filtros = request.GET.copy()
    filtros.pop("page", None)
    return render(request, "hallazgos/buscar.html", {"form": form, "page_obj": Paginator(qs, 25).get_page(request.GET.get("page")), "filtros": filtros.urlencode(), "seguimiento": request.GET.get("seguimiento") == "1", "titulo": "Seguimiento" if request.GET.get("seguimiento") else "Buscar hallazgos"})


@login_required
def hallazgo_detalle(request, pk):
    h = obtener_hallazgo(request.user, pk)
    ciclo = h.ciclo_actual
    gestionar = puede_gestionar(request.user, h)
    actividades = list(ciclo.acciones.select_related("responsable").prefetch_related("eventos") if ciclo else [])
    en_tratamiento = h.estado in {"ACCION_INMEDIATA", "EN_ANALISIS", "PBI_EN_GESTION", "PLAN_ACCION", "EN_IMPLEMENTACION", "REABIERTO"}
    for a in actividades:
        a.puede_actualizar = en_tratamiento and a.estado != "COMPLETADA" and (gestionar or (a.responsable_id == request.user.pk and request.user.has_perm("accounts.registrar_hallazgo")))
    autor = request.user.has_perm("accounts.registrar_hallazgo") and request.user.pk in {h.registrado_por_id, h.responsable_id}
    historial = Paginator(h.historial.select_related("usuario"), 20).get_page(request.GET.get("page"))
    context = {
        "hallazgo": h, "ciclo": ciclo, "timeline": timeline_hallazgo(h),
        "transiciones": acciones_disponibles(request.user, h), "acciones": actividades,
        "gestionar": gestionar and en_tratamiento, "puede_editar": (autor and h.estado in {"BORRADOR", "DEVUELTO"}) or (puede_validar(request.user, h) and h.estado == "PENDIENTE_VALIDACION"),
        "puede_causa": gestionar and h.estado == "EN_ANALISIS",
        "puede_accion": gestionar and h.estado in {"ACCION_INMEDIATA", "REABIERTO", "PLAN_ACCION"},
        "puede_pbi": gestionar and h.estado in {"PBI_EN_GESTION", "PLAN_ACCION", "EN_IMPLEMENTACION"} and h.origen_tecnologico,
        "puede_evaluar": puede_validar(request.user, h) and request.user.has_perm("accounts.evaluar_eficacia") and h.estado == "EN_VERIFICACION",
        "puede_evidencia": h.estado not in {"CERRADO", "CANCELADO"} and (gestionar or autor),
        "historial": historial,
        "evidencias": h.evidencias.select_related("subido_por")[:50],
        "ciclos": h.ciclos.prefetch_related("evaluaciones__evaluador", "acciones__responsable", "comunicaciones", "pbis"),
    }
    return render(request, "hallazgos/detalle.html", context)


@login_required
def hallazgo_transicion(request, pk, accion):
    h = obtener_hallazgo(request.user, pk)
    disponibles = dict(acciones_disponibles(request.user, h))
    if accion not in disponibles:
        raise PermissionDenied
    form = TransicionForm(request.POST or None, initial={"version": h.version})
    return completar_formulario(request, form, disponibles[accion], lambda d: WorkflowService.ejecutar(usuario=request.user, hallazgo=h, accion=accion, comentario=d.get("comentario", ""), version=d.get("version")), h,
        aviso=f"Estado actual: {h.get_estado_display()}. Se comprobarán los requisitos antes de confirmar.",
        peligro="Esta decisión queda registrada en el historial. Indica el motivo y confirma la acción." if accion in {"cerrar", "cancelar", "devolver", "reabrir"} else "")


@login_required
def hallazgo_causa(request, pk):
    h = obtener_hallazgo(request.user, pk)
    exigir_gestion(request.user, h)
    if h.estado != "EN_ANALISIS":
        raise PermissionDenied
    ciclo = h.ciclo_actual
    analisis = ciclo
    form = AnalisisCausaForm(request.POST or None, instance=analisis)
    if request.method == "POST" and form.is_valid():
        finalizar = request.POST.get("finalizar") == "1"
        try:
            with transaction.atomic():
                CausaService.guardar(usuario=request.user, hallazgo=h, datos=form.datos_servicio(), finalizar=finalizar)
                if finalizar:
                    h = WorkflowService.completar_analisis(usuario=request.user, hallazgo=h)
        except ValidationError as error:
            errores(form, error)
        else:
            if finalizar:
                messages.success(request, "Checklist completado. El paso 3 está habilitado.")
                if h.estado == "PBI_EN_GESTION":
                    return redirect("hallazgo_pbi", pk=pk)
                return redirect("hallazgo_accion", pk=pk)
            messages.success(request, "Checklist guardado. Puedes continuar completándolo.")
            return redirect("hallazgo_causa", pk=pk)
    grupos = []
    abrir_error = True
    intento_finalizar = request.method == "POST" and request.POST.get("finalizar") == "1"
    for grupo in form.categorias:
        preguntas = [{"obj": p["pregunta"], "texto": p["texto"], "respuesta": p["respuesta"], "comentario": p["comentario"]} for p in grupo["preguntas"]]
        tiene_error = any(x["respuesta"].errors or x["comentario"].errors for x in preguntas)
        incompleto = intento_finalizar and any(not x["respuesta"].value() for x in preguntas)
        abrir = abrir_error and (tiene_error or incompleto)
        if abrir:
            abrir_error = False
        grupos.append({"categoria": grupo["categoria"], "preguntas": preguntas, "abrir": abrir})
    return render(request, "hallazgos/causa.html", {"hallazgo": h, "ciclo": ciclo, "form": form, "grupos": grupos, "campos_control": [form[n] for n in form.fields if n.startswith("control_")], "timeline": timeline_hallazgo(h)})


@login_required
def hallazgo_accion(request, pk):
    h = obtener_hallazgo(request.user, pk)
    exigir_gestion(request.user, h)
    form = AccionForm(request.POST or None, initial={"tipo": "CORRECTIVA" if h.estado == "PLAN_ACCION" else "INMEDIATA", "fecha_inicio": timezone.localdate()})
    return completar_formulario(request, form, "Registrar acción", lambda d: AccionService.crear(usuario=request.user, hallazgo=h, datos=d), h)


def obtener_accion(usuario, pk):
    a = get_object_or_404(Accion.objects.select_related("ciclo__hallazgo", "responsable").prefetch_related("eventos"), pk=pk)
    if not puede_ver(usuario, a.hallazgo):
        raise Http404
    if not puede_gestionar(usuario, a.hallazgo) and not (a.responsable_id == usuario.pk and usuario.has_perm("accounts.registrar_hallazgo")):
        raise PermissionDenied
    return a


@login_required
def accion_seguimiento(request, pk):
    a = obtener_accion(request.user, pk)
    form = SeguimientoForm(request.POST or None, initial={"estado": a.estado, "porcentaje_avance": a.porcentaje_avance, "fecha_real": a.fecha_real})
    return completar_formulario(request, form, "Registrar seguimiento", lambda d: AccionService.seguir(usuario=request.user, accion=a, datos=d), a.hallazgo, accion=a)


@login_required
def accion_reprogramar(request, pk):
    a = obtener_accion(request.user, pk)
    form = ReprogramacionForm(request.POST or None)
    return completar_formulario(request, form, "Reprogramar acción", lambda d: AccionService.reprogramar(usuario=request.user, accion=a, **d), a.hallazgo, accion=a, aviso="Se conserva la FET inicial y cada cambio de fecha. Se permiten hasta tres reprogramaciones por acción.")


@login_required
def hallazgo_eficacia(request, pk):
    h = obtener_hallazgo(request.user, pk)
    if not puede_validar(request.user, h) or not request.user.has_perm("accounts.evaluar_eficacia"):
        raise PermissionDenied
    form = EvaluacionEficaciaForm(request.POST or None, initial={"fecha_evaluacion": timezone.localdate()})
    return completar_formulario(request, form, "Evaluar eficacia", lambda d: EficaciaService.evaluar(usuario=request.user, hallazgo=h, datos=d), h, aviso="Eficaz habilita el cierre. No eficaz abre un nuevo ciclo y conserva el tratamiento anterior.")


@login_required
def hallazgo_pbi(request, pk):
    h = obtener_hallazgo(request.user, pk)
    exigir_gestion(request.user, h)
    form = PBIForm(request.POST or None)
    return completar_formulario(request, form, "Registrar referencia PBI", lambda d: PBIService.guardar(usuario=request.user, hallazgo=h, datos=d), h, aviso="Registra la referencia del PBI gestionado en Helix. Esta pantalla no crea ni envía tickets externos.")


@login_required
def hallazgo_comunicacion(request, pk):
    h = obtener_hallazgo(request.user, pk)
    exigir_gestion(request.user, h)
    form = ComunicacionForm(request.POST or None, initial={"fecha": timezone.localtime().strftime("%Y-%m-%dT%H:%M")})
    return completar_formulario(request, form, "Registrar comunicación", lambda d: ComunicacionService.registrar(usuario=request.user, hallazgo=h, datos=d), h, aviso="Deja constancia de una comunicación ya realizada: destinatarios, medio, fecha y contenido.")


@login_required
def hallazgo_evidencia(request, pk):
    h = obtener_hallazgo(request.user, pk)
    form = EvidenciaForm(request.POST or None, request.FILES or None, hallazgo=h)
    return completar_formulario(request, form, "Adjuntar evidencia", lambda d: EvidenciaService.subir(usuario=request.user, hallazgo=h, **d), h, multipart=True, aviso="PDF, PNG o JPEG de hasta 10 MB. La descarga requiere acceso al caso.")


@login_required
def evidencia_descargar(request, pk):
    evidencia = get_object_or_404(Evidencia.objects.select_related("hallazgo__proceso"), pk=pk)
    if not puede_ver(request.user, evidencia.hallazgo):
        raise Http404
    try:
        respuesta = FileResponse(evidencia.archivo.open("rb"), as_attachment=True, filename=evidencia.nombre_original, content_type=evidencia.mime_type)
    except FileNotFoundError as error:
        raise Http404("La evidencia no está disponible.") from error
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Cache-Control"] = "private, no-store"
    return respuesta


@login_required
def notificaciones(request):
    qs = request.user.notificaciones.filter(hallazgo__in=hallazgos_visibles(request.user)).select_related("hallazgo")
    return render(request, "hallazgos/notificaciones.html", {"pagina": Paginator(qs, 25).get_page(request.GET.get("page"))})


@login_required
@require_POST
def notificacion_leer(request, pk):
    aviso = get_object_or_404(Notificacion, pk=pk, usuario=request.user, hallazgo__in=hallazgos_visibles(request.user))
    if not aviso.leida:
        aviso.leida, aviso.fecha_lectura = True, timezone.now()
        aviso.save(update_fields=["leida", "fecha_lectura"])
    return redirect("hallazgo_detalle", pk=aviso.hallazgo_id)
