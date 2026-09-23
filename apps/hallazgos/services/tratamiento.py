from django.db import transaction
from django.utils import timezone
from apps.hallazgos.models import ComunicacionHallazgo, EvaluacionEficacia, PBI
from .common import (bloquear, campos_permitidos, ciclo_vigente, editable, exigir,
    gestionar, notificar, nuevo_ciclo, registrar, tratamiento_completo, validar)


class PBIService:
    @staticmethod
    @transaction.atomic
    def guardar(*, usuario, hallazgo, datos):
        hallazgo = bloquear(hallazgo)
        gestionar(usuario, hallazgo)
        editable(hallazgo, {"PBI_EN_GESTION", "PLAN_ACCION", "EN_IMPLEMENTACION"})
        exigir(hallazgo.es_critica == "SI" and hallazgo.origen_tecnologico, "El registro PBI aplica al caso crítico tecnológico.")
        campos_permitidos(datos, ["numero_pbi", "ticket_incidente", "sistema", "herramienta", "responsable_ti", "estado", "fecha_cierre", "observacion"])
        ciclo = ciclo_vigente(hallazgo)
        exigir(bool(datos.get("numero_pbi", "").strip()), "Indique la referencia PBI.")
        exigir(datos.get("responsable_ti") and datos["responsable_ti"].is_active, "Seleccione un responsable TI activo.")
        exigir(datos.get("estado", "ABIERTO") in {"ABIERTO", "CERRADO"}, "Estado de PBI no válido.")
        cerrado = datos.get("estado") == "CERRADO"
        fecha = datos.get("fecha_cierre")
        exigir((cerrado and fecha is not None) or (not cerrado and fecha is None), "El PBI cerrado requiere fecha de cierre; el abierto no debe tenerla.")
        if fecha:
            exigir(fecha <= timezone.localdate(), "La fecha de cierre PBI no puede estar en el futuro.")
        pbi = PBI.objects.filter(ciclo=ciclo, numero_pbi=datos["numero_pbi"]).first()
        antes = {campo: str(getattr(pbi, campo)) for campo in datos} if pbi else {}
        if pbi is None:
            pbi = PBI(ciclo=ciclo)
        for campo, valor in datos.items():
            setattr(pbi, campo, valor)
        pbi.full_clean()
        pbi.save()
        registrar(hallazgo, usuario, "REGISTRO_PBI", metadata={"pbi": pbi.numero_pbi, "antes": antes, "despues": {campo: str(getattr(pbi, campo)) for campo in datos}, "integracion": "manual"})
        return pbi


class ComunicacionService:
    @staticmethod
    @transaction.atomic
    def registrar(*, usuario, hallazgo, datos):
        hallazgo = bloquear(hallazgo)
        gestionar(usuario, hallazgo)
        editable(hallazgo)
        campos_permitidos(datos, ["destinatarios", "medio", "descripcion", "fecha"])
        comunicacion = ComunicacionHallazgo(ciclo=ciclo_vigente(hallazgo), registrado_por=usuario, **datos)
        exigir(comunicacion.fecha <= timezone.now(), "La comunicación registrada no puede ser futura.")
        comunicacion.full_clean()
        comunicacion.save()
        registrar(hallazgo, usuario, "COMUNICACION", comunicacion.descripcion, metadata={"destinatarios": comunicacion.destinatarios, "medio": comunicacion.medio, "envio_externo": False})
        return comunicacion


class EficaciaService:
    @staticmethod
    @transaction.atomic
    def evaluar(*, usuario, hallazgo, datos):
        hallazgo = bloquear(hallazgo)
        validar(usuario, hallazgo, "evaluar_eficacia")
        editable(hallazgo, {"EN_VERIFICACION"})
        campos_permitidos(datos, ["fecha_evaluacion", "resultado", "comentario"])
        ciclo = tratamiento_completo(hallazgo)
        fecha = datos.get("fecha_evaluacion")
        exigir(fecha is not None and timezone.localtime(ciclo.fecha_inicio).date() <= fecha <= timezone.localdate(), "La fecha de evaluación debe estar entre el inicio del ciclo y hoy.")
        exigir(bool(datos.get("comentario", "").strip()), "Fundamente el resultado de la evaluación.")
        evaluacion = EvaluacionEficacia(ciclo=ciclo, evaluador=usuario, **datos)
        evaluacion.full_clean()
        evaluacion.save()
        anterior = hallazgo.estado
        if evaluacion.resultado == "NO_EFICAZ":
            nuevo_ciclo(hallazgo, usuario, f"Tratamiento no eficaz: {evaluacion.comentario}")
            hallazgo.estado = "REABIERTO"
        registrar(hallazgo, usuario, "EVALUACION_EFICACIA", evaluacion.comentario, anterior=anterior, metadata={"resultado": evaluacion.resultado, "ciclo": ciclo.numero, "evaluacion": evaluacion.pk})
        notificar(hallazgo, "evaluacion_eficacia", f"Resultado: {evaluacion.get_resultado_display()}. {evaluacion.comentario}")
        return evaluacion
