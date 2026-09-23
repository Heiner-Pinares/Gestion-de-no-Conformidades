"""Consultas con alcance por usuario; compartidas por búsqueda, panel y reportes."""
from django.db.models import Count, Q
from django.utils import timezone
from apps.accounts.permissions import puede_gestionar, puede_validar
from .models import EvaluacionEficacia, Hallazgo
from .services.workflow import TRANSICIONES


def hallazgos_visibles(usuario):
    consulta = Hallazgo.objects.select_related("tipo_registro", "fuente_deteccion", "proceso", "subproceso", "responsable", "registrado_por", "prioridad", "urgencia")
    if not usuario.is_authenticated or not usuario.is_active:
        return consulta.none()
    if usuario.has_perm("accounts.ver_todos_hallazgos"):
        return consulta
    alcance = Q(registrado_por=usuario) | Q(responsable=usuario) | Q(ciclos__acciones__responsable=usuario)
    if usuario.has_perm("accounts.validar_hallazgo"):
        alcance |= Q(proceso__validadores=usuario)
    return consulta.filter(alcance).distinct()


def acciones_disponibles(usuario, hallazgo):
    acciones = []
    for codigo, (origenes, destino, etiqueta) in TRANSICIONES.items():
        # El flujo nuevo avanza desde el formulario de identificación. Estas
        # transiciones se conservan solo para datos históricos y compatibilidad.
        if codigo in {"enviar", "devolver", "validar", "cancelar", "iniciar_inmediata", "iniciar_analisis"}:
            continue
        if hallazgo.estado not in origenes:
            continue
        if codigo in {"validar", "devolver", "cancelar"} and not puede_validar(usuario, hallazgo):
            continue
        if codigo in {"cerrar", "reabrir"}:
            permiso = "cerrar_hallazgo" if codigo == "cerrar" else "evaluar_eficacia"
            if not puede_validar(usuario, hallazgo) or not usuario.has_perm(f"accounts.{permiso}"):
                continue
            if codigo == "cerrar":
                ciclo = hallazgo.ciclo_actual
                ultima = ciclo.evaluaciones.first() if ciclo else None
                if not ultima or ultima.resultado != "EFICAZ":
                    continue
        if codigo == "enviar":
            if usuario.pk not in {hallazgo.registrado_por_id, hallazgo.responsable_id} or not usuario.has_perm("accounts.registrar_hallazgo"):
                continue
        elif codigo not in {"validar", "devolver", "cancelar", "cerrar", "reabrir"} and not puede_gestionar(usuario, hallazgo):
            continue
        if codigo == "planificar" and hallazgo.es_critica != "SI":
            continue
        if codigo == "iniciar_pbi" and not hallazgo.origen_tecnologico:
            continue
        if codigo == "planificar" and hallazgo.origen_tecnologico and hallazgo.estado != "PBI_EN_GESTION":
            continue
        if codigo == "enviar_verificacion" and hallazgo.es_critica == "SI" and hallazgo.estado != "EN_IMPLEMENTACION":
            continue
        acciones.append((codigo, etiqueta))
    return acciones


def timeline_hallazgo(hallazgo):
    """Cuatro etapas del prototipo v8; los estados internos no añaden pasos visuales."""
    etiquetas = [
        ("Identificación", ""),
        ("Análisis de causa raíz", ""),
        ("Solución inmediata", "y acciones correctivas"),
        ("Evaluación de eficacia", "y cierre"),
    ]
    estado = hallazgo.estado
    if estado in {"EN_ANALISIS", "PBI_EN_GESTION"}:
        actual = 2
    elif estado in {"ACCION_INMEDIATA", "REABIERTO", "PLAN_ACCION", "EN_IMPLEMENTACION"}:
        actual = 3
    elif estado in {"EN_VERIFICACION", "CERRADO"}:
        actual = 4
    else:
        actual = 1
    estados = ["Pendiente"] * 4
    estados[actual - 1] = "Actual"
    if actual > 1:
        estados[0] = "Completado"
    # Una corrección inmediata puede preceder al análisis: no marcarlo realizado.
    if estado in {"PLAN_ACCION", "EN_IMPLEMENTACION", "EN_VERIFICACION", "CERRADO"}:
        estados[1] = "Completado"
    if estado in {"EN_VERIFICACION", "CERRADO"}:
        estados[2] = "Completado"
    if estado == "CERRADO":
        estados[3] = "Completado"
    if estado == "CANCELADO":
        estados[0] = "Cancelado"
    return [
        {"etiqueta": etiqueta, "linea2": linea2, "estado": estados[i],
         "bloqueado": i >= 2 and estados[i] == "Pendiente"}
        for i, (etiqueta, linea2) in enumerate(etiquetas)
    ]


def indicadores(usuario):
    consulta = hallazgos_visibles(usuario)
    hoy = timezone.localdate()
    datos = consulta.aggregate(
        total=Count("pk", distinct=True),
        borradores=Count("pk", filter=Q(estado="BORRADOR"), distinct=True),
        abiertos=Count("pk", filter=~Q(estado__in=["CERRADO", "CANCELADO"]), distinct=True),
        pendientes=Count("pk", filter=Q(estado="PENDIENTE_VALIDACION"), distinct=True),
        en_analisis=Count("pk", filter=Q(estado__in=["EN_ANALISIS", "PBI_EN_GESTION"]), distinct=True),
        en_verificacion=Count("pk", filter=Q(estado="EN_VERIFICACION"), distinct=True),
        cerrados=Count("pk", filter=Q(estado="CERRADO"), distinct=True),
        criticos=Count("pk", filter=Q(es_critica="SI"), distinct=True),
        vencidos=Count("pk", filter=Q(fecha_solucion__lt=hoy) & ~Q(estado__in=["CERRADO", "CANCELADO"]), distinct=True),
        devueltos=Count("pk", filter=Q(estado="DEVUELTO"), distinct=True),
        validados=Count("pk", filter=Q(estado="VALIDADO"), distinct=True),
    )
    evaluaciones = EvaluacionEficacia.objects.filter(ciclo__hallazgo__in=consulta.values("pk"))
    total = evaluaciones.count()
    datos["porcentaje_eficacia"] = round(100 * evaluaciones.filter(resultado="EFICAZ").count() / total, 1) if total else 0
    datos["eficacia"] = datos["porcentaje_eficacia"]
    return datos
