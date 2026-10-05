"""Guards y auditoría compartidos. Orden de locks: hallazgo, después acción."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Max
from django.utils import timezone

from apps.accounts.permissions import puede_gestionar, puede_validar
from apps.hallazgos.models import CicloTratamiento, Hallazgo, HistorialHallazgo, Notificacion

TRATAMIENTO = {"ACCION_INMEDIATA", "EN_ANALISIS", "PBI_EN_GESTION", "PLAN_ACCION", "EN_IMPLEMENTACION", "EN_VERIFICACION", "REABIERTO"}


def bloquear(hallazgo, version=None):
    actual = Hallazgo.objects.select_for_update().get(pk=hallazgo.pk)
    if version is not None and int(version) != actual.version:
        raise ValidationError("El registro cambió desde que lo abrió. Recargue antes de guardar.")
    return actual


def exigir(condicion, mensaje):
    if not condicion:
        raise ValidationError(mensaje)


def gestionar(usuario, hallazgo):
    if not puede_gestionar(usuario, hallazgo):
        raise PermissionDenied("No tiene permiso para gestionar este hallazgo.")


def validar(usuario, hallazgo, permiso="validar_hallazgo"):
    if not usuario.has_perm(f"accounts.{permiso}") or not puede_validar(usuario, hallazgo):
        raise PermissionDenied("Se requiere un validador asignado al proceso, distinto del reportante.")


def editable(hallazgo, estados=TRATAMIENTO):
    exigir(hallazgo.estado in estados, "Esta operación no está disponible en el estado actual.")


def ciclo_vigente(hallazgo, contexto=None):
    ciclo = hallazgo.ciclo_actual
    exigir(ciclo is not None and ciclo.fecha_fin is None, "No existe un plan de compromisos activo.")
    if contexto is not None:
        exigir(contexto.ciclo_id == ciclo.pk, "Los planes anteriores son históricos y no se pueden modificar.")
    return ciclo


def registrar(hallazgo, usuario, accion, comentario="", anterior=None, metadata=None, accion_relacionada=None):
    hallazgo.version += 1
    hallazgo.updated_by = usuario
    hallazgo.save(update_fields=["estado", "version", "updated_by", "updated_at"])
    return HistorialHallazgo.objects.create(hallazgo=hallazgo, usuario=usuario, accion=accion, accion_relacionada=accion_relacionada,
        estado_anterior=anterior if anterior is not None else hallazgo.estado,
        estado_nuevo=hallazgo.estado, comentario=comentario, metadata_json=metadata or {})


def notificar(hallazgo, tipo, mensaje, destinatarios=None):
    ids = destinatarios if destinatarios is not None else {hallazgo.registrado_por_id, hallazgo.responsable_id}
    Notificacion.objects.bulk_create([Notificacion(usuario_id=uid, hallazgo=hallazgo, tipo=tipo,
        titulo=f"{hallazgo.codigo} · {tipo.replace('_', ' ').capitalize()}", mensaje=mensaje) for uid in set(ids) if uid])


def nuevo_ciclo(hallazgo, usuario, motivo):
    anterior = hallazgo.ciclo_actual
    if anterior and anterior.fecha_fin is None:
        anterior.fecha_fin = timezone.now()
        anterior.save(update_fields=["fecha_fin"])
    return CicloTratamiento.objects.create(hallazgo=hallazgo, numero=(anterior.numero + 1 if anterior else 1), motivo=motivo, creado_por=usuario)


def campos_permitidos(datos, campos):
    desconocidos = set(datos) - set(campos)
    exigir(not desconocidos, f"Campos no permitidos: {', '.join(sorted(desconocidos))}.")


def requiere_inmediata(ciclo):
    acciones = ciclo.acciones.filter(tipo="INMEDIATA").exclude(estado="CANCELADA")
    exigir(acciones.exists() and not acciones.exclude(estado="COMPLETADA").exists(), "Termine al menos una solución inmediata y todas las soluciones inmediatas vigentes del plan.")


def analisis_completo(ciclo):
    return ciclo.analisis_fin is not None


def actividades_completas(ciclo):
    """El paso 4 solo se habilita cuando cada actividad llegó al 100 %."""
    acciones = ciclo.acciones.exclude(estado="CANCELADA")
    return acciones.exists() and not acciones.exclude(
        estado="COMPLETADA", porcentaje_avance=100
    ).exists()


def tratamiento_completo(hallazgo):
    from django.conf import settings
    ciclo = ciclo_vigente(hallazgo)
    exigir(
        actividades_completas(ciclo),
        "Termine todas las actividades al 100 % antes de pasar a la evaluación de eficacia. Las canceladas no se consideran.",
    )
    requiere_inmediata(ciclo)
    if hallazgo.es_critica == "SI":
        exigir(analisis_completo(ciclo), "Finalice el análisis de causa del plan.")
        exigir(ciclo.acciones.filter(tipo="CORRECTIVA").exclude(estado="CANCELADA").exists(), "Registre al menos una acción correctiva vigente.")
        if hallazgo.origen_tecnologico:
            exigir(ciclo.pbis.exists(), "Registre la referencia PBI para el caso crítico tecnológico.")
            if getattr(settings, "REQUIRE_CLOSED_PBI", False):
                exigir(not ciclo.pbis.exclude(estado="CERRADO").exists(), "Cierre los PBI antes de continuar.")
    return ciclo
