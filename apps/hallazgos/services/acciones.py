from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.accounts.permissions import puede_gestionar
from apps.hallazgos.models import Accion
from .common import (bloquear, campos_permitidos, ciclo_vigente, editable, exigir,
    gestionar, notificar, registrar)

CAMPOS_ACCION = ["tipo", "descripcion", "responsable", "fecha_inicio", "fet_inicial", "resultado_esperado", "comentario"]


def bloquear_accion(usuario, accion):
    hallazgo = bloquear(accion.ciclo.hallazgo)
    accion = Accion.objects.select_for_update().get(pk=accion.pk)
    if not puede_gestionar(usuario, hallazgo) and not (accion.responsable_id == usuario.pk and usuario.has_perm("accounts.registrar_hallazgo")):
        raise PermissionDenied("No tiene autorización sobre esta acción.")
    editable(hallazgo)
    ciclo_vigente(hallazgo, accion)
    exigir(accion.estado != "COMPLETADA", "Una acción completada es histórica; cree una nueva acción en el ciclo correspondiente.")
    return hallazgo, accion


class AccionService:
    @staticmethod
    @transaction.atomic
    def crear(*, usuario, hallazgo, datos):
        hallazgo = bloquear(hallazgo)
        gestionar(usuario, hallazgo)
        campos_permitidos(datos, CAMPOS_ACCION)
        tipo = datos.get("tipo")
        if tipo == "INMEDIATA":
            editable(hallazgo, {"ACCION_INMEDIATA", "REABIERTO", "PLAN_ACCION"})
        elif tipo == "CORRECTIVA":
            editable(hallazgo, {"PLAN_ACCION"})
            exigir(hallazgo.es_critica == "SI", "Las acciones correctivas no aplican al caso no crítico.")
        else:
            exigir(False, "Seleccione un tipo de acción válido.")
        ciclo = ciclo_vigente(hallazgo)
        exigir(datos.get("responsable") and datos["responsable"].is_active, "Seleccione un responsable activo.")
        exigir(datos.get("fet_inicial") and datos.get("fecha_inicio"), "Indique las fechas de inicio y compromiso.")
        exigir(datos["fet_inicial"] >= timezone.localdate(), "La fecha compromiso inicial no puede ser anterior a hoy.")
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
            exigir(avance == 100 and fecha_real is not None, "Una acción completada requiere 100% de avance y fecha real.")
            exigir(accion.fecha_inicio <= fecha_real <= timezone.localdate(), "La fecha real debe estar entre el inicio y hoy.")
        else:
            exigir(avance < 100 and fecha_real is None, "Una acción abierta no puede tener 100% ni fecha real de finalización.")
            exigir(estado != "PENDIENTE" or avance == 0, "Una acción pendiente debe tener avance 0%.")
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
