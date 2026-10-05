"""Adaptadores HTTP. Las reglas y transacciones pertenecen a services."""
from datetime import timedelta
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from apps.accounts.permissions import es_administrador, puede_gestionar, puede_validar, puede_ver
from apps.catalogos.models import CategoriaCausa
from .forms import (
    AccionForm, ActividadPlanForm, AnalisisCausaForm, BuscarHallazgoForm, ComunicacionForm,
    EvaluacionEficaciaForm, EvidenciaForm, HallazgoForm, PBIForm,
    ReprogramacionForm, SeguimientoForm, SeguimientoLineaForm, TransicionForm,
)
from .models import Accion, Evidencia, Hallazgo, HistorialHallazgo, Notificacion
from .selectors import acciones_disponibles, hallazgos_visibles, indicadores, timeline_hallazgo
from .services import (
    AccionService, CausaService, CodigoSACService, ComunicacionService, EficaciaService,
    EvidenciaService, HallazgoService, PBIService, WorkflowService,
)


def obtener_hallazgo(usuario, pk):
    return get_object_or_404(hallazgos_visibles(usuario), pk=pk)


def preparar_historial_hallazgo(pagina, hallazgo):
    """Añade presentación legible a la auditoría sin alterar los datos guardados."""
    tipos = {
        "EVALUACION_EFICACIA": ("evaluacion", "Evaluación de eficacia"),
        "SEGUIMIENTO_ACCION": ("seguimiento", "Seguimiento de compromiso"),
        "EVIDENCIA": ("evidencia", "Evidencia adjunta"),
        "REPROGRAMACION": ("reprogramacion", "Reprogramación aprobada"),
        "SOLICITUD_REPROGRAMACION": ("reprogramacion", "Solicitud de reprogramación"),
        "REPROGRAMACION_RECHAZADA": ("alerta", "Reprogramación rechazada"),
        "CREAR_ACCION": ("seguimiento", "Compromiso registrado"),
        "COMUNICACION": ("evidencia", "Comunicación registrada"),
        "REGISTRO_PBI": ("evidencia", "Referencia PBI registrada"),
        "FINALIZAR_ANALISIS": ("evaluacion", "Análisis de causa finalizado"),
        "GUARDAR_ANALISIS": ("seguimiento", "Análisis de causa actualizado"),
        "CREACION": ("general", "Hallazgo creado"),
        "ACTUALIZACION": ("general", "Identificación actualizada"),
        "DEVOLVER": ("alerta", "Corrección solicitada"),
        "CANCELAR": ("alerta", "Hallazgo cancelado"),
    }
    transiciones = {
        "ENVIAR", "VALIDAR", "INICIAR_INMEDIATA", "INICIAR_ANALISIS",
        "INICIAR_PBI", "PLANIFICAR", "INICIAR_IMPLEMENTACION",
        "ENVIAR_VERIFICACION", "CERRAR", "REABRIR",
        "CONTINUAR_IDENTIFICACION", "COMPLETAR_ANALISIS",
    }
    eventos = list(pagina.object_list)
    evidencia_ids = {
        evento.metadata_json.get("evidencia")
        for evento in eventos
        if evento.accion == "EVIDENCIA" and evento.metadata_json.get("evidencia")
    }
    evidencias = {
        evidencia.pk: evidencia
        for evidencia in hallazgo.evidencias.filter(pk__in=evidencia_ids)
    }
    for evento in eventos:
        evento.historial_tipo, evento.historial_etiqueta = tipos.get(
            evento.accion,
            ("transicion", "Transición de estado") if evento.accion in transiciones else ("general", "Detalle"),
        )
        evento.evidencia_detalle = evidencias.get(evento.metadata_json.get("evidencia"))
    pagina.object_list = eventos
    return pagina


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


def contexto_registro(form, *, hallazgo=None, **extra):
    contexto = {"form": form, "hallazgo": hallazgo, **extra}
    if hallazgo is not None:
        codigos = {
            str(tipo.pk): CodigoSACService.previsualizar(tipo=tipo)
            for tipo in form.fields["tipo_registro"].queryset
        }
        tipo_guardado_id = Hallazgo.objects.values_list("tipo_registro_id", flat=True).get(pk=hallazgo.pk)
        codigos[str(tipo_guardado_id)] = hallazgo.codigo
        seleccionado = form["tipo_registro"].value()
        contexto.update(
            codigos_sac=codigos,
            codigo_previsualizado=codigos.get(str(seleccionado), hallazgo.codigo),
        )
        return contexto
    codigos = {
        str(tipo.pk): CodigoSACService.previsualizar(tipo=tipo)
        for tipo in form.fields["tipo_registro"].queryset
    }
    seleccionado = form["tipo_registro"].value()
    contexto.update(codigos_sac=codigos, codigo_previsualizado=codigos.get(str(seleccionado), ""))
    return contexto


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
    plantilla = "administrador/inicio.html" if es_administrador(request.user) else "hallazgos/inicio.html"
    contexto = {"recientes": qs[:8], "resumen": resumen}
    if es_administrador(request.user):
        hoy = timezone.localdate()
        inicio_mes = hoy.replace(day=1)
        fin_mes_anterior = inicio_mes - timedelta(days=1)
        inicio_mes_anterior = fin_mes_anterior.replace(day=1)

        def variacion(consulta, *, favorable_al_subir=True):
            actual = consulta.filter(fecha_registro__date__gte=inicio_mes).count()
            anterior = consulta.filter(
                fecha_registro__date__gte=inicio_mes_anterior,
                fecha_registro__date__lte=fin_mes_anterior,
            ).count()
            if anterior:
                porcentaje = round(abs(actual - anterior) * 100 / anterior)
            else:
                porcentaje = 100 if actual else 0
            direccion = "up" if actual > anterior else "down" if actual < anterior else "flat"
            favorable = direccion == ("up" if favorable_al_subir else "down")
            return {
                "porcentaje": porcentaje,
                "direccion": direccion,
                "simbolo": "↑" if direccion == "up" else "↓" if direccion == "down" else "−",
                "clase": "positive" if favorable else "negative" if direccion != "flat" else "neutral",
            }

        metricas = [
            {
                "valor": resumen["total"], "etiqueta": "Total hallazgos",
                "detalle": "Registros del sistema", "tono": "blue", "icono": "document",
                **variacion(qs),
            },
            {
                "valor": resumen["pendientes"], "etiqueta": "Pendientes",
                "detalle": "Requieren atención", "tono": "amber", "icono": "clock",
                **variacion(qs.exclude(estado__in=["CERRADO", "CANCELADO"]), favorable_al_subir=False),
            },
            {
                "valor": resumen["en_analisis"], "etiqueta": "En análisis",
                "detalle": "Análisis de causa raíz", "tono": "purple", "icono": "settings",
                **variacion(qs.filter(estado__in=["EN_ANALISIS", "PBI_EN_GESTION"]), favorable_al_subir=False),
            },
            {
                "valor": resumen["cerrados"], "etiqueta": "Cerrados",
                "detalle": "Gestión finalizada", "tono": "green", "icono": "check",
                **variacion(qs.filter(estado="CERRADO")),
            },
        ]
        contexto["metricas_admin"] = metricas
    return render(request, plantilla, contexto)


def ayuda(request):
    return render(request, "ayuda.html")


@login_required
def hallazgo_crear(request):
    if not request.user.has_perm("accounts.registrar_hallazgo"):
        raise PermissionDenied
    form = HallazgoForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            hallazgo = HallazgoService.crear(usuario=request.user, datos=form.cleaned_data, borrador=False)
        except ValidationError as error:
            errores(form, error)
        else:
            destino = "análisis de causa raíz" if hallazgo.estado == "EN_ANALISIS" else "solución inmediata"
            messages.success(request, f"{hallazgo.codigo} avanzó a {destino}.")
            return redirigir_siguiente_paso(hallazgo)
    return render(request, "hallazgos/registro.html", contexto_registro(
        form,
        titulo="Registro de Solicitud de Acción Correctiva",
        timeline=timeline_hallazgo(Hallazgo(estado="BORRADOR")),
    ))


@login_required
def hallazgo_editar(request, pk):
    hallazgo = obtener_hallazgo(request.user, pk)
    autor = request.user.has_perm("accounts.registrar_hallazgo") and request.user.pk in [hallazgo.registrado_por_id, hallazgo.responsable_id]
    revisor = puede_validar(request.user, hallazgo) and hallazgo.estado == "PENDIENTE_VALIDACION"
    ciclo = hallazgo.ciclo_actual
    accion_sin_actividades = hallazgo.estado == "ACCION_INMEDIATA" and ciclo is not None and not ciclo.acciones.exists()
    if not ((autor and (hallazgo.estado in ["BORRADOR", "DEVUELTO", "EN_ANALISIS"] or accion_sin_actividades)) or revisor):
        raise PermissionDenied
    version = hallazgo.version
    form = HallazgoForm(request.POST or None, instance=hallazgo, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            version = forms.IntegerField(min_value=1).clean(request.POST.get("version"))
            with transaction.atomic():
                actualizado = HallazgoService.actualizar(
                    usuario=request.user, hallazgo=hallazgo, datos=form.cleaned_data,
                    version=version, completo=request.POST.get("accion") == "continuar",
                )
                if request.POST.get("accion") == "continuar" and actualizado.estado in {"BORRADOR", "DEVUELTO"}:
                    actualizado = WorkflowService.continuar_identificacion(usuario=request.user, hallazgo=actualizado)
                hallazgo = actualizado
        except ValidationError as error:
            errores(form, error)
        else:
            messages.success(request, "Identificación actualizada con trazabilidad.")
            if request.POST.get("accion") == "continuar":
                return redirigir_siguiente_paso(hallazgo)
            return redirect("hallazgo_detalle", pk=pk)
    return render(request, "hallazgos/registro.html", contexto_registro(
        form,
        hallazgo=hallazgo,
        version=version,
        titulo="Corregir identificación",
        timeline=timeline_hallazgo(hallazgo),
    ))


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
    es_admin = es_administrador(request.user)
    plantilla = "administrador/hallazgos.html" if es_admin else "hallazgos/buscar.html"
    return render(request, plantilla, {
        "form": form,
        "page_obj": Paginator(qs, 10 if es_admin else 25).get_page(request.GET.get("page")),
        "filtros": filtros.urlencode(),
    })


@login_required
def validaciones_admin(request):
    """Bandeja administrativa del paso 4; no interviene en la identificación."""
    if not es_administrador(request.user):
        raise PermissionDenied
    qs = hallazgos_visibles(request.user).filter(estado="EN_VERIFICACION")
    prioridad = request.GET.get("prioridad", "").strip()
    desde = request.GET.get("desde", "").strip()
    hasta = request.GET.get("hasta", "").strip()
    if prioridad:
        qs = qs.filter(prioridad_snapshot=prioridad)
    if desde:
        qs = qs.filter(fecha_registro__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha_registro__date__lte=hasta)

    casos = list(qs.order_by("-fecha_registro"))
    listos = 0
    for hallazgo in casos:
        ciclo = hallazgo.ciclo_actual
        ultima = ciclo.evaluaciones.first() if ciclo else None
        actividades_vigentes = ciclo.acciones.exclude(estado="CANCELADA") if ciclo else None
        hallazgo.listo_para_cierre = bool(
            ciclo
            and actividades_vigentes.exists()
            and not actividades_vigentes.exclude(estado="COMPLETADA", porcentaje_avance=100).exists()
            and ultima
            and ultima.resultado == "EFICAZ"
        )
        listos += hallazgo.listo_para_cierre
    pagina = Paginator(casos, 8).get_page(request.GET.get("page"))
    filtros = request.GET.copy()
    filtros.pop("page", None)
    return render(request, "administrador/validaciones.html", {
        "pagina": pagina,
        "filtros": filtros.urlencode(),
        "prioridad": prioridad,
        "desde": desde,
        "hasta": hasta,
        "resumen_validaciones": {
            "pendientes": len(casos),
            "listos": listos,
            "en_revision": len(casos) - listos,
            "cerrados": hallazgos_visibles(request.user).filter(estado="CERRADO").count(),
        },
    })


@login_required
def hallazgo_detalle(request, pk):
    h = obtener_hallazgo(request.user, pk)
    ciclo = h.ciclo_actual
    gestionar = puede_gestionar(request.user, h)
    actividades = list(
        ciclo.acciones.select_related("responsable").prefetch_related(
            Prefetch(
                "eventos",
                queryset=HistorialHallazgo.objects.select_related("usuario").order_by("-fecha_hora", "-pk"),
            ),
            "evidencias",
        )
        if ciclo else []
    )
    en_tratamiento = h.estado in {"ACCION_INMEDIATA", "EN_ANALISIS", "PBI_EN_GESTION", "PLAN_ACCION", "EN_IMPLEMENTACION", "REABIERTO"}
    for a in actividades:
        a.historial_compacto = [
            evento for evento in a.eventos.all()
            if evento.accion in {"SEGUIMIENTO_ACCION", "REPROGRAMACION"}
        ]
        evidencias_accion = list(a.evidencias.all())
        evidencias_por_id = {evidencia.pk: evidencia for evidencia in evidencias_accion}
        eventos_por_id = {evento.pk: evento for evento in a.eventos.all()}
        evidencias_usadas = set()
        for evento in a.historial_compacto:
            metadata = evento.metadata_json or {}
            ids = list(metadata.get("evidencia_ids") or [])
            if metadata.get("evidencia_id"):
                ids.append(metadata["evidencia_id"])
            solicitud = eventos_por_id.get(metadata.get("solicitud_id"))
            metadata_solicitud = solicitud.metadata_json or {} if solicitud else {}
            if metadata_solicitud.get("evidencia_id"):
                ids.append(metadata_solicitud["evidencia_id"])
            evento.evidencias_detalle = [
                evidencias_por_id[evidencia_id]
                for evidencia_id in dict.fromkeys(ids)
                if evidencia_id in evidencias_por_id
            ]
            if not evento.evidencias_detalle and evento.accion == "SEGUIMIENTO_ACCION":
                descripcion = f"Seguimiento: {evento.comentario.strip()}"
                candidatas = [
                    evidencia for evidencia in evidencias_accion
                    if evidencia.pk not in evidencias_usadas and evidencia.descripcion == descripcion
                ]
                if candidatas:
                    evento.evidencias_detalle = [min(
                        candidatas,
                        key=lambda evidencia: abs((evidencia.fecha_carga - evento.fecha_hora).total_seconds()),
                    )]
            evidencias_usadas.update(evidencia.pk for evidencia in evento.evidencias_detalle)
        a.reprogramaciones_count = sum(
            evento.accion == "REPROGRAMACION" for evento in a.historial_compacto
        )
        a.puede_actualizar = en_tratamiento and a.estado not in {"COMPLETADA", "CANCELADA"} and (gestionar or (a.responsable_id == request.user.pk and request.user.has_perm("accounts.registrar_hallazgo")))
        a.solicitud_reprogramacion = next((evento for evento in a.eventos.all()
            if evento.accion == "SOLICITUD_REPROGRAMACION" and evento.metadata_json.get("estado") == "PENDIENTE"), None)
        a.puede_aprobar_reprogramacion = bool(
            a.solicitud_reprogramacion
            and a.solicitud_reprogramacion.metadata_json.get("aprobador_id") == request.user.pk
        )
    autor = request.user.has_perm("accounts.registrar_hallazgo") and request.user.pk in {h.registrado_por_id, h.responsable_id}
    historial = preparar_historial_hallazgo(
        Paginator(h.historial.select_related("usuario"), 20).get_page(request.GET.get("page")),
        h,
    )
    transiciones = acciones_disponibles(request.user, h)
    ultima_evaluacion = ciclo.evaluaciones.first() if ciclo else None
    actividades_vigentes = [a for a in actividades if a.estado != "CANCELADA"]
    total_actividades = len(actividades_vigentes)
    actividades_completadas = sum(
        a.estado == "COMPLETADA" and a.porcentaje_avance == 100 for a in actividades_vigentes
    )
    cierre_listo = bool(
        h.estado == "EN_VERIFICACION"
        and total_actividades > 0
        and actividades_completadas == total_actividades
        and ultima_evaluacion
        and ultima_evaluacion.resultado == "EFICAZ"
    )
    context = {
        "hallazgo": h, "ciclo": ciclo, "timeline": timeline_hallazgo(h),
        "transiciones": [(codigo, etiqueta) for codigo, etiqueta in transiciones if codigo != "cerrar"],
        "acciones": actividades,
        "gestionar": gestionar and en_tratamiento, "puede_editar": (autor and (h.estado in {"BORRADOR", "DEVUELTO", "EN_ANALISIS"} or (h.estado == "ACCION_INMEDIATA" and ciclo is not None and not ciclo.acciones.exists()))) or (puede_validar(request.user, h) and h.estado == "PENDIENTE_VALIDACION"),
        "puede_causa": gestionar and h.estado == "EN_ANALISIS",
        "puede_accion": gestionar and h.estado in {"ACCION_INMEDIATA", "REABIERTO", "PLAN_ACCION", "EN_IMPLEMENTACION"},
        "puede_pbi": gestionar and h.estado in {"PBI_EN_GESTION", "PLAN_ACCION", "EN_IMPLEMENTACION"} and h.origen_tecnologico,
        "puede_evaluar": puede_validar(request.user, h) and request.user.has_perm("accounts.evaluar_eficacia") and h.estado == "EN_VERIFICACION",
        "historial": historial,
        "ciclos": h.ciclos.prefetch_related("evaluaciones__evaluador", "acciones__responsable", "comunicaciones", "pbis"),
        "mostrar_cierre_administrativo": h.estado == "EN_VERIFICACION",
        "es_administrador": es_administrador(request.user),
        "cierre_listo": cierre_listo,
        "puede_aprobar_cierre": cierre_listo and any(codigo == "cerrar" for codigo, _ in transiciones),
        "ultima_evaluacion": ultima_evaluacion,
        "total_actividades": total_actividades,
        "actividades_completadas": actividades_completadas,
        "reprogramacion_form": ReprogramacionForm(solicitante=request.user),
    }
    return render(request, "hallazgos/detalle.html", context)


@login_required
def hallazgo_transicion(request, pk, accion):
    h = obtener_hallazgo(request.user, pk)
    disponibles = dict(acciones_disponibles(request.user, h))
    if accion not in disponibles:
        raise PermissionDenied
    form = TransicionForm(request.POST or None, initial={"version": h.version})
    if accion == "cerrar":
        form.fields["comentario"].required = True
        form.fields["comentario"].label = "Comentario del visto bueno"
        form.fields["confirmar"].label = "Confirmo el visto bueno y el cierre definitivo del hallazgo."
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
        otro = grupo.get("otro")
        tiene_error_otro = bool(otro and (otro["texto"].errors or otro["respuesta"].errors or otro["comentario"].errors))
        tiene_error = any(x["respuesta"].errors or x["comentario"].errors for x in preguntas) or tiene_error_otro
        incompleto = intento_finalizar and any(not x["respuesta"].value() for x in preguntas)
        abrir = abrir_error and (tiene_error or incompleto)
        if abrir:
            abrir_error = False
        grupos.append({"categoria": grupo["categoria"], "preguntas": preguntas, "otro": otro, "abrir": abrir})
    return render(request, "hallazgos/causa.html", {"hallazgo": h, "ciclo": ciclo, "form": form, "grupos": grupos, "campos_control": [form[n] for n in form.fields if n.startswith("control_")], "timeline": timeline_hallazgo(h)})


@login_required
def hallazgo_accion(request, pk):
    h = obtener_hallazgo(request.user, pk)
    exigir_gestion(request.user, h)
    if h.estado not in {"ACCION_INMEDIATA", "REABIERTO", "PLAN_ACCION", "EN_IMPLEMENTACION"}:
        raise PermissionDenied
    ActividadFormSet = forms.formset_factory(ActividadPlanForm, extra=0, can_delete=True, min_num=1, validate_min=True)
    ciclo = h.ciclo_actual
    acciones_existentes = ciclo.acciones.count()
    tipos_existentes = set(
        ciclo.acciones.exclude(estado="CANCELADA").values_list("tipo", flat=True)
    )
    if acciones_existentes:
        requiere_correctiva = h.estado == "PLAN_ACCION" and h.es_critica == "SI" and not ciclo.acciones.filter(tipo="CORRECTIVA").exclude(estado="CANCELADA").exists()
        inicial = [{
            "tipo": "CORRECTIVA",
            "descripcion": "Definir acción correctiva" if requiere_correctiva else "",
            "estado": "PENDIENTE",
            "fet_inicial": timezone.localdate(),
        }]
    else:
        inicial = [{"tipo": "INMEDIATA", "descripcion": "Registrar solución inmediata", "estado": "PENDIENTE", "fet_inicial": timezone.localdate()}]
    formset = ActividadFormSet(
        request.POST or None,
        initial=inicial if request.method == "GET" else None,
        prefix="actividades",
        form_kwargs={"es_critica": h.es_critica == "SI"},
    )
    if request.method == "POST" and formset.is_valid():
        formularios = [f for f in formset.forms if f.cleaned_data and not f.cleaned_data.get("DELETE")]
        try:
            tipos = set(tipos_existentes)
            tipos.update(f.cleaned_data["tipo"] for f in formularios)
            if h.es_critica == "SI" and not {"INMEDIATA", "CORRECTIVA"}.issubset(tipos):
                raise ValidationError(
                    "No puedes guardar todavía: una no conformidad crítica debe incluir como mínimo "
                    "una Solución inmediata y una Acción correctiva."
                )
            if h.es_critica != "SI" and "INMEDIATA" not in tipos:
                raise ValidationError(
                    "No puedes guardar todavía: una no conformidad no crítica debe incluir como mínimo "
                    "una Solución inmediata."
                )
            with transaction.atomic():
                for formulario in formularios:
                    AccionService.crear(usuario=request.user, hallazgo=h, datos=formulario.datos_servicio())
                h.refresh_from_db()
                if h.estado == "PLAN_ACCION":
                    h = WorkflowService.ejecutar(usuario=request.user, hallazgo=h, accion="iniciar_implementacion")
        except ValidationError as error:
            formset._non_form_errors = formset.error_class(error.messages)
        else:
            return redirect("hallazgo_acciones_creadas", pk=h.pk)
    siguiente = acciones_existentes + 1
    return render(request, "hallazgos/plan_actividades.html", {
        "hallazgo": h, "formset": formset, "timeline": timeline_hallazgo(h), "siguiente_numero": siguiente,
        "puede_volver_identificacion": acciones_existentes == 0,
        "modo_adicional": acciones_existentes > 0,
        "requiere_accion_correctiva": h.es_critica == "SI",
        "tiene_solucion_inmediata": "INMEDIATA" in tipos_existentes,
        "tiene_accion_correctiva": "CORRECTIVA" in tipos_existentes,
    })


@login_required
def hallazgo_acciones_creadas(request, pk):
    h = obtener_hallazgo(request.user, pk)
    ciclo = h.ciclo_actual
    acciones = ciclo.acciones.select_related("responsable").prefetch_related("eventos") if ciclo else Accion.objects.none()
    return render(request, "hallazgos/actividades_creadas.html", {"hallazgo": h, "acciones": acciones})


@login_required
def hallazgo_acciones_seguimiento(request, pk):
    h = obtener_hallazgo(request.user, pk)
    exigir_gestion(request.user, h)
    ciclo = h.ciclo_actual
    acciones = list(ciclo.acciones.select_related("responsable").prefetch_related("eventos") if ciclo else [])
    lineas = []
    todos_validos = True
    for accion in acciones:
        prefijo = f"accion-{accion.pk}"
        formulario = None if accion.estado in {"COMPLETADA", "CANCELADA"} else SeguimientoLineaForm(
            request.POST or None,
            prefix=prefijo,
            accion=accion,
            initial={"estado": accion.estado, "fecha_real": accion.fecha_real},
        )
        if request.method == "POST" and formulario is not None:
            todos_validos = formulario.is_valid() and todos_validos
        fechas = [e.metadata_json.get("nueva_fecha", "—") for e in accion.reprogramaciones]
        fechas += ["—"] * (3 - len(fechas))
        lineas.append({"accion": accion, "form": formulario, "reprogramaciones": fechas[:3]})
    error_general = ""
    accion_solicitada = request.POST.get("accion", "guardar")
    if request.method == "POST" and accion_solicitada not in {"guardar", "evaluar"}:
        error_general = "La acción solicitada no es válida."
    elif request.method == "POST" and todos_validos:
        try:
            with transaction.atomic():
                for linea in lineas:
                    accion, formulario = linea["accion"], linea["form"]
                    if formulario is None:
                        continue
                    estado = formulario.cleaned_data["estado"]
                    fecha_real = formulario.cleaned_data.get("fecha_real")
                    if estado != accion.estado or fecha_real != accion.fecha_real:
                        avance = 100 if estado == "COMPLETADA" else (50 if estado == "EN_PROCESO" else 0)
                        AccionService.seguir(usuario=request.user, accion=accion, datos={
                            "estado": estado,
                            "porcentaje_avance": avance,
                            "fecha_real": fecha_real,
                            "comentario": "Actualización registrada desde el seguimiento de actividades.",
                        })
                h.refresh_from_db()
                if accion_solicitada == "evaluar" and h.estado != "EN_VERIFICACION":
                    WorkflowService.ejecutar(usuario=request.user, hallazgo=h, accion="enviar_verificacion")
        except ValidationError as error:
            error_general = " ".join(error.messages)
        else:
            if accion_solicitada == "evaluar":
                return redirect("hallazgo_eficacia", pk=h.pk)
            messages.success(request, "El seguimiento de las actividades fue guardado.")
            return redirect("hallazgo_acciones_seguimiento", pk=h.pk)
    actividades_vigentes = [a for a in acciones if a.estado != "CANCELADA"]
    total = len(actividades_vigentes)
    completadas = sum(a.estado == "COMPLETADA" for a in actividades_vigentes)
    progreso = round(100 * completadas / total) if total else 0
    return render(request, "hallazgos/seguimiento_actividades.html", {
        "hallazgo": h, "lineas": lineas, "total": total, "completadas": completadas,
        "progreso": progreso, "puede_evaluar": total > 0 and completadas == total,
        "pendientes": total - completadas, "error_general": error_general,
    })


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
    ahora = timezone.localtime().replace(second=0, microsecond=0)
    form = SeguimientoForm(
        request.POST or None,
        request.FILES or None,
        accion=a,
        initial={"porcentaje_avance": a.porcentaje_avance, "fecha_seguimiento": ahora},
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                actualizada = AccionService.seguir(
                    usuario=request.user,
                    accion=a,
                    datos=form.datos_servicio(),
                )
                archivo = form.cleaned_data.get("archivo")
                if archivo:
                    evidencia = EvidenciaService.subir(
                        usuario=request.user,
                        hallazgo=actualizada.hallazgo,
                        accion=actualizada,
                        archivo=archivo,
                        descripcion=f"Seguimiento: {form.cleaned_data['comentario'].strip()}",
                    )
                    seguimiento = actualizada.seguimientos.filter(usuario=request.user).order_by(
                        "-fecha_hora", "-pk"
                    ).first()
                    metadata = dict(seguimiento.metadata_json or {})
                    metadata["evidencia_ids"] = list(dict.fromkeys([
                        *(metadata.get("evidencia_ids") or []), evidencia.pk,
                    ]))
                    seguimiento.metadata_json = metadata
                    seguimiento.save(update_fields=["metadata_json"])
        except ValidationError as error:
            errores(form, error)
        else:
            messages.success(request, f"El seguimiento de {a.codigo} fue guardado.")
            return redirect("hallazgo_detalle", pk=a.hallazgo.pk)
    return render(request, "hallazgos/seguimiento_accion.html", {
        "form": form,
        "hallazgo": a.hallazgo,
        "accion": a,
        "fecha_seguimiento": ahora,
    })


@login_required
def accion_reprogramar(request, pk):
    a = obtener_accion(request.user, pk)
    form = ReprogramacionForm(request.POST or None, request.FILES or None, solicitante=request.user, accion=a)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                solicitud = AccionService.solicitar_reprogramacion(
                    usuario=request.user, accion=a,
                    nueva_fecha=form.cleaned_data["nueva_fecha"],
                    motivo=form.cleaned_data["motivo"],
                    aprobador=form.cleaned_data["aprobador"],
                )
                archivo = form.cleaned_data.get("archivo")
                if archivo:
                    evidencia = EvidenciaService.subir(
                        usuario=request.user, hallazgo=a.hallazgo, accion=a, archivo=archivo,
                        descripcion=f"Solicitud de reprogramación: {form.cleaned_data['motivo'].strip()}",
                    )
                    metadata = dict(solicitud.metadata_json)
                    metadata["evidencia_id"] = evidencia.pk
                    solicitud.metadata_json = metadata
                    solicitud.save(update_fields=["metadata_json"])
        except ValidationError as error:
            errores(form, error)
        else:
            messages.success(request, f"La solicitud para reprogramar {a.codigo} fue enviada a aprobación.")
            return redirect("hallazgo_detalle", pk=a.hallazgo.pk)
    return render(request, "hallazgos/reprogramacion_accion.html", {
        "form": form, "hallazgo": a.hallazgo, "accion": a,
    })


@login_required
@require_POST
def accion_reprogramacion_resolver(request, pk, decision):
    if decision not in {"aprobar", "rechazar"}:
        raise Http404
    solicitud = get_object_or_404(
        HistorialHallazgo.objects.select_related("accion_relacionada__ciclo__hallazgo"),
        pk=pk, accion="SOLICITUD_REPROGRAMACION",
    )
    hallazgo = solicitud.hallazgo
    try:
        AccionService.resolver_reprogramacion(
            usuario=request.user, solicitud_id=solicitud.pk, aprobar=decision == "aprobar",
        )
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        resultado = "aprobada" if decision == "aprobar" else "rechazada"
        messages.success(request, f"La solicitud de reprogramación fue {resultado}.")
    return redirect("hallazgo_detalle", pk=hallazgo.pk)


@login_required
def hallazgo_eficacia(request, pk):
    h = obtener_hallazgo(request.user, pk)
    autorizado = (puede_validar(request.user, h) and request.user.has_perm("accounts.evaluar_eficacia")) or puede_gestionar(request.user, h)
    if not autorizado or h.estado != "EN_VERIFICACION":
        raise PermissionDenied
    ciclo = h.ciclo_actual
    actividades_vigentes = ciclo.acciones.exclude(estado="CANCELADA") if ciclo else None
    if not ciclo or not actividades_vigentes.exists() or actividades_vigentes.exclude(
        estado="COMPLETADA", porcentaje_avance=100
    ).exists():
        messages.error(request, "Termine todas las actividades al 100 % antes de pasar a la evaluación de eficacia. Las canceladas no se consideran.")
        return redirect("hallazgo_acciones_seguimiento", pk=h.pk)
    form = EvaluacionEficaciaForm(request.POST or None, initial={"fecha_evaluacion": timezone.localdate()})
    if request.method == "POST" and form.is_valid():
        try:
            EficaciaService.evaluar(usuario=request.user, hallazgo=h, datos=form.cleaned_data)
        except ValidationError as error:
            errores(form, error)
        else:
            messages.success(request, "La evaluación de eficacia fue guardada correctamente.")
            return redirect("hallazgo_detalle", pk=h.pk)
    acciones = list(h.ciclo_actual.acciones.exclude(estado="CANCELADA").prefetch_related("eventos"))
    total = len(acciones)
    completadas = sum(a.estado == "COMPLETADA" for a in acciones)
    eficiencia = round(sum(a.eficiencia for a in acciones) / total) if total else 0
    return render(request, "hallazgos/eficacia.html", {
        "hallazgo": h, "form": form, "timeline": timeline_hallazgo(h), "total": total,
        "completadas": completadas, "abiertas": total - completadas, "eficiencia": eficiencia,
    })


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
        respuesta = FileResponse(
            evidencia.archivo.open("rb"),
            as_attachment=request.GET.get("ver") != "1",
            filename=evidencia.nombre_original,
            content_type=evidencia.mime_type,
        )
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
