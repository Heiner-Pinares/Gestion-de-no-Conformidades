from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from apps.accounts.permissions import puede_gestionar
from apps.hallazgos.models import Accion, HistorialHallazgo
from .common import (bloquear, campos_permitidos, ciclo_vigente, editable, exigir,
    gestionar, notificar, registrar)

CAMPOS_ACCION = ["tipo", "descripcion", "responsable", "fecha_inicio", "fet_inicial", "estado", "resultado_esperado", "comentario"]


def bloquear_accion(usuario, accion):
    hallazgo = bloquear(accion.ciclo.hallazgo)
    accion = Accion.objects.select_for_update().get(pk=accion.pk)
    if not puede_gestionar(usuario, hallazgo) and not (accion.responsable_id == usuario.pk and usuario.has_perm("accounts.registrar_hallazgo")):
        raise PermissionDenied("No tiene autorización sobre esta acción.")
    editable(hallazgo)
    ciclo_vigente(hallazgo, accion)
    exigir(accion.estado not in {"COMPLETADA", "CANCELADA"}, "Una acción terminada o cancelada es histórica; cree una nueva acción en el plan correspondiente.")
    return hallazgo, accion


class AccionService:
    @staticmethod
    @transaction.atomic
    def crear(*, usuario, hallazgo, datos):
        hallazgo = bloquear(hallazgo)
        gestionar(usuario, hallazgo)
        campos_permitidos(datos, CAMPOS_ACCION)
        tipo = datos.get("tipo")
        if tipo in {"INMEDIATA", "ACCION_INMEDIATA"}:
            editable(hallazgo, {"ACCION_INMEDIATA", "REABIERTO", "PLAN_ACCION", "EN_IMPLEMENTACION"})
        elif tipo == "CORRECTIVA":
            editable(hallazgo, {"ACCION_INMEDIATA", "REABIERTO", "PLAN_ACCION", "EN_IMPLEMENTACION"})
        else:
            exigir(False, "Seleccione un tipo de acción válido.")
        ciclo = ciclo_vigente(hallazgo)
        responsable = datos.get("responsable")
        exigir(responsable is not None and responsable.is_active, "Seleccione un responsable activo.")
        exigir(datos.get("fecha_inicio"), "Indique la fecha de inicio.")
        exigir(datos.get("fet_inicial"), "Indique la fecha de compromiso.")
        exigir(datos["fet_inicial"] >= timezone.localdate(), "La fecha compromiso inicial no puede ser anterior a hoy.")
        estado = datos.get("estado", "PENDIENTE")
        exigir(estado in dict(Accion.ESTADOS), "Estado de acción no válido.")
        datos = {**datos, "estado": estado}
        if estado == "COMPLETADA":
            datos.update(porcentaje_avance=100, fecha_real=timezone.localdate())
        elif estado == "EN_PROCESO":
            datos.update(porcentaje_avance=50, fecha_real=None)
        else:
            datos.update(porcentaje_avance=0, fecha_real=None)
        numero = Accion.objects.filter(ciclo__hallazgo=hallazgo).count() + 1
        accion = Accion(ciclo=ciclo, codigo=f"{hallazgo.codigo}-A{numero:02d}", fecha_vigente=datos["fet_inicial"], **datos)
        accion.full_clean()
        accion.save()
        registrar(hallazgo, usuario, "CREAR_ACCION", metadata={"accion": accion.codigo, "tipo": accion.tipo, "ciclo": ciclo.numero})
        notificar(hallazgo, "accion_asignada", f"Se le asignó {accion.codigo}: {accion.descripcion}", {accion.responsable_id})
        return accion

    @staticmethod
    @transaction.atomic
    def seguir(*, usuario, accion, datos):
        hallazgo, accion = bloquear_accion(usuario, accion)
        campos_permitidos(datos, ["estado", "porcentaje_avance", "fecha_real", "comentario"])
        exigir(bool(datos.get("comentario", "").strip()), "Registre un comentario de seguimiento.")
        estado = datos.get("estado")
        avance = datos.get("porcentaje_avance")
        exigir(estado in dict(Accion.ESTADOS), "Estado de acción no válido.")
        exigir(isinstance(avance, int) and 0 <= avance <= 100, "El avance debe estar entre 0 y 100.")
        fecha_real = datos.get("fecha_real")
        if estado == "COMPLETADA":
            exigir(avance == 100 and fecha_real is not None, "Una acción terminada requiere 100% de avance y fecha real.")
            exigir(accion.fecha_inicio <= fecha_real <= timezone.localdate(), "La fecha real debe estar entre el inicio y hoy.")
        else:
            exigir(avance < 100 and fecha_real is None, "Una acción no terminada no puede tener 100% ni fecha real de finalización.")
            exigir(estado != "PENDIENTE" or avance == 0, "Una acción pendiente debe tener avance 0%.")
            exigir(estado != "CANCELADA" or avance == 0, "Una acción cancelada debe tener avance 0%.")
        accion.estado, accion.porcentaje_avance, accion.fecha_real = estado, avance, fecha_real
        accion.comentario = datos["comentario"]
        accion.full_clean()
        accion.save()
        registrar(hallazgo, usuario, "SEGUIMIENTO_ACCION", datos["comentario"], accion_relacionada=accion, metadata={"accion": accion.codigo, "estado": estado, "avance": avance, "fecha_real": str(fecha_real)})
        return accion

    @staticmethod
    @transaction.atomic
    def reprogramar(*, usuario, accion, nueva_fecha, motivo):
        hallazgo, accion = bloquear_accion(usuario, accion)
        exigir(bool(motivo.strip()), "Debe justificar la reprogramación.")
        numero = accion.reprogramaciones.count() + 1
        exigir(numero <= 3, "La actividad alcanzó el máximo permitido de reprogramaciones.")
        exigir(nueva_fecha is not None and nueva_fecha >= timezone.localdate() and nueva_fecha >= accion.fecha_inicio, "La nueva fecha debe ser desde hoy y no anterior al inicio.")
        exigir(nueva_fecha != accion.fecha_vigente, "La nueva fecha debe ser distinta de la fecha vigente.")
        fecha_anterior = accion.fecha_vigente
        accion.fecha_vigente = nueva_fecha
        accion.save(update_fields=["fecha_vigente", "updated_at"])
        registrar(hallazgo, usuario, "REPROGRAMACION", motivo, accion_relacionada=accion, metadata={"accion": accion.codigo, "numero": numero, "fecha_anterior": str(fecha_anterior), "nueva_fecha": str(nueva_fecha)})
        notificar(hallazgo, "reprogramacion", f"La acción {accion.codigo} tiene fecha vigente {nueva_fecha}.", {accion.responsable_id})
        return accion

    @staticmethod
    @transaction.atomic
    def solicitar_reprogramacion(*, usuario, accion, nueva_fecha, motivo, aprobador):
        hallazgo, accion = bloquear_accion(usuario, accion)
        motivo = motivo.strip()
        exigir(bool(motivo), "Debe justificar la reprogramación.")
        exigir(aprobador is not None and aprobador.is_active, "Seleccione un responsable de jefatura activo.")
        exigir(aprobador.pk != usuario.pk, "La solicitud debe ser aprobada por otra persona.")
        pendiente = accion.eventos.filter(
            accion="SOLICITUD_REPROGRAMACION", metadata_json__estado="PENDIENTE",
        ).exists()
        exigir(not pendiente, "La acción ya tiene una solicitud de reprogramación pendiente.")
        numero = accion.reprogramaciones.count() + 1
        exigir(numero <= 3, "La actividad alcanzó el máximo permitido de reprogramaciones.")
        exigir(nueva_fecha is not None and nueva_fecha >= timezone.localdate() and nueva_fecha >= accion.fecha_inicio,
               "La nueva fecha debe ser desde hoy y no anterior al inicio.")
        exigir(nueva_fecha != accion.fecha_vigente, "La nueva fecha debe ser distinta de la fecha vigente.")
        solicitud = registrar(
            hallazgo, usuario, "SOLICITUD_REPROGRAMACION", motivo, accion_relacionada=accion,
            metadata={
                "accion": accion.codigo, "numero": numero, "estado": "PENDIENTE",
                "fecha_anterior": str(accion.fecha_vigente) if accion.fecha_vigente else "",
                "nueva_fecha": str(nueva_fecha), "aprobador_id": aprobador.pk,
                "aprobador": aprobador.get_full_name() or aprobador.username,
                "aprobador_cargo": aprobador.cargo,
            },
        )
        notificar(
            hallazgo, "aprobacion_reprogramacion",
            f"{usuario} solicita reprogramar {accion.codigo} para el {nueva_fecha}. Revisa el caso para aprobar o rechazar.",
            {aprobador.pk},
        )
        return solicitud

    @staticmethod
    @transaction.atomic
    def resolver_reprogramacion(*, usuario, solicitud_id, aprobar):
        referencia = HistorialHallazgo.objects.select_related("accion_relacionada__ciclo__hallazgo").get(
            pk=solicitud_id, accion="SOLICITUD_REPROGRAMACION",
        )
        accion_id = referencia.accion_relacionada_id
        hallazgo = bloquear(referencia.hallazgo)
        accion = Accion.objects.select_for_update().get(pk=accion_id)
        solicitud = HistorialHallazgo.objects.select_for_update().get(pk=solicitud_id)
        metadata = dict(solicitud.metadata_json or {})
        exigir(metadata.get("estado") == "PENDIENTE", "La solicitud ya fue atendida.")
        if metadata.get("aprobador_id") != usuario.pk:
            raise PermissionDenied("Solo el responsable seleccionado puede resolver esta solicitud.")
        editable(hallazgo)
        ciclo_vigente(hallazgo, accion)
        exigir(accion.estado not in {"COMPLETADA", "CANCELADA"}, "La acción ya no admite reprogramaciones.")
        solicitante_id = solicitud.usuario_id
        if aprobar:
            numero = accion.reprogramaciones.count() + 1
            exigir(numero <= 3, "La actividad alcanzó el máximo permitido de reprogramaciones.")
            try:
                nueva_fecha = date.fromisoformat(metadata.get("nueva_fecha", ""))
            except (TypeError, ValueError) as exc:
                raise ValidationError("La fecha propuesta no es válida.") from exc
            exigir(nueva_fecha >= timezone.localdate() and nueva_fecha >= accion.fecha_inicio,
                   "La fecha propuesta venció o es anterior al inicio; solicita una nueva reprogramación.")
            exigir(nueva_fecha != accion.fecha_vigente, "La fecha propuesta ya coincide con la fecha vigente.")
            fecha_anterior = accion.fecha_vigente
            accion.fecha_vigente = nueva_fecha
            accion.full_clean()
            accion.save(update_fields=["fecha_vigente", "updated_at"])
            metadata.update(estado="APROBADA", resuelto_por_id=usuario.pk, resuelto_por=str(usuario),
                            fecha_resolucion=timezone.now().isoformat())
            solicitud.metadata_json = metadata
            solicitud.save(update_fields=["metadata_json"])
            registrar(
                hallazgo, usuario, "REPROGRAMACION", solicitud.comentario, accion_relacionada=accion,
                metadata={"accion": accion.codigo, "numero": numero, "solicitud_id": solicitud.pk,
                          "fecha_anterior": str(fecha_anterior) if fecha_anterior else "", "nueva_fecha": str(nueva_fecha)},
            )
            mensaje = f"La reprogramación de {accion.codigo} fue aprobada. Nueva fecha vigente: {nueva_fecha}."
            estado = "aprobada"
        else:
            metadata.update(estado="RECHAZADA", resuelto_por_id=usuario.pk, resuelto_por=str(usuario),
                            fecha_resolucion=timezone.now().isoformat())
            solicitud.metadata_json = metadata
            solicitud.save(update_fields=["metadata_json"])
            registrar(
                hallazgo, usuario, "REPROGRAMACION_RECHAZADA", solicitud.comentario,
                accion_relacionada=accion, metadata={"accion": accion.codigo, "solicitud_id": solicitud.pk},
            )
            mensaje = f"La solicitud de reprogramación de {accion.codigo} fue rechazada."
            estado = "rechazada"
        notificar(hallazgo, f"reprogramacion_{estado}", mensaje, {solicitante_id, accion.responsable_id})
        return accion
