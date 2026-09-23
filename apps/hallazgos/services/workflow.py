from django.db import transaction
from django.utils import timezone
from .common import (analisis_completo, bloquear, ciclo_vigente, exigir, gestionar,
    notificar, nuevo_ciclo, registrar, requiere_inmediata, tratamiento_completo, validar)
from .hallazgo import validar_datos

TRANSICIONES = {
    "enviar": ({"BORRADOR", "DEVUELTO"}, "PENDIENTE_VALIDACION", "Enviar a validación"),
    "devolver": ({"PENDIENTE_VALIDACION"}, "DEVUELTO", "Solicitar corrección"),
    "validar": ({"PENDIENTE_VALIDACION"}, "VALIDADO", "Validar hallazgo"),
    "cancelar": ({"PENDIENTE_VALIDACION"}, "CANCELADO", "No corresponde"),
    "iniciar_inmediata": ({"VALIDADO", "REABIERTO"}, "ACCION_INMEDIATA", "Iniciar acción inmediata"),
    "iniciar_analisis": ({"ACCION_INMEDIATA", "REABIERTO"}, "EN_ANALISIS", "Iniciar análisis de causa"),
    "iniciar_pbi": ({"EN_ANALISIS"}, "PBI_EN_GESTION", "Iniciar gestión PBI"),
    "planificar": ({"EN_ANALISIS", "PBI_EN_GESTION"}, "PLAN_ACCION", "Pasar al plan de acción"),
    "iniciar_implementacion": ({"PLAN_ACCION"}, "EN_IMPLEMENTACION", "Iniciar implementación"),
    "enviar_verificacion": ({"ACCION_INMEDIATA", "EN_IMPLEMENTACION"}, "EN_VERIFICACION", "Enviar a verificación"),
    "cerrar": ({"EN_VERIFICACION"}, "CERRADO", "Cerrar hallazgo"),
    "reabrir": ({"CERRADO"}, "REABIERTO", "Reabrir tratamiento"),
}


class WorkflowService:
    @staticmethod
    @transaction.atomic
    def continuar_identificacion(*, usuario, hallazgo, version=None):
        """Avanza desde identificación sin una aprobación administrativa intermedia."""
        from django.core.exceptions import PermissionDenied

        hallazgo = bloquear(hallazgo, version)
        exigir(hallazgo.estado in {"BORRADOR", "DEVUELTO"}, "La identificación ya fue continuada.")
        if usuario.pk not in {hallazgo.registrado_por_id, hallazgo.responsable_id} or not usuario.has_perm("accounts.registrar_hallazgo"):
            raise PermissionDenied("Solo el reportante o responsable puede continuar el hallazgo.")
        validar_datos(hallazgo, completo=True)
        hallazgo.save()
        if not hallazgo.ciclo_actual:
            nuevo_ciclo(hallazgo, usuario, "Tratamiento inicial")
        anterior = hallazgo.estado
        hallazgo.estado = "EN_ANALISIS"
        registrar(
            hallazgo,
            usuario,
            "CONTINUAR_IDENTIFICACION",
            "Flujo directo desde identificación; no requiere validación administrativa.",
            anterior=anterior,
        )
        notificar(
            hallazgo,
            "identificacion_completada",
            "Identificación completada. El tratamiento puede continuar.",
        )
        return hallazgo

    @staticmethod
    @transaction.atomic
    def completar_analisis(*, usuario, hallazgo):
        """Cierra el paso 2 y habilita la solución del paso 3."""
        hallazgo = bloquear(hallazgo)
        gestionar(usuario, hallazgo)
        exigir(hallazgo.estado == "EN_ANALISIS", "El análisis no está disponible en el estado actual.")
        ciclo = ciclo_vigente(hallazgo)
        exigir(analisis_completo(ciclo), "Complete el checklist antes de habilitar el paso 3.")
        anterior = hallazgo.estado
        if hallazgo.es_critica == "SI" and hallazgo.origen_tecnologico:
            hallazgo.estado = "PBI_EN_GESTION"
        elif hallazgo.es_critica == "SI":
            hallazgo.estado = "PLAN_ACCION"
        else:
            hallazgo.estado = "ACCION_INMEDIATA"
        registrar(
            hallazgo,
            usuario,
            "COMPLETAR_ANALISIS",
            "Checklist 6M completado; paso 3 habilitado.",
            anterior=anterior,
        )
        notificar(hallazgo, "analisis_completado", "Análisis de causa completado. El paso 3 está habilitado.")
        return hallazgo

    @staticmethod
    @transaction.atomic
    def ejecutar(*, usuario, hallazgo, accion, comentario="", version=None):
        hallazgo = bloquear(hallazgo, version)
        exigir(accion in TRANSICIONES, "La transición solicitada no existe.")
        origenes, destino, etiqueta = TRANSICIONES[accion]
        exigir(hallazgo.estado in origenes, "La transición no está permitida desde el estado actual.")
        if accion in {"devolver", "validar", "cancelar"}:
            validar(usuario, hallazgo)
        elif accion in {"cerrar", "reabrir"}:
            validar(usuario, hallazgo, "cerrar_hallazgo" if accion == "cerrar" else "evaluar_eficacia")
        elif accion == "enviar":
            from django.core.exceptions import PermissionDenied
            if usuario.pk not in {hallazgo.registrado_por_id, hallazgo.responsable_id} or not usuario.has_perm("accounts.registrar_hallazgo"):
                raise PermissionDenied("Solo el reportante o responsable puede enviar el hallazgo.")
        else:
            gestionar(usuario, hallazgo)
        if accion in {"devolver", "cancelar", "cerrar", "reabrir"}:
            exigir(bool(comentario.strip()), "Es obligatorio registrar el motivo u observación.")
        if accion in {"enviar", "validar"}:
            validar_datos(hallazgo, completo=True, fecha_cambiada=(accion == "enviar"))
            hallazgo.save()
        elif accion == "iniciar_inmediata":
            if not hallazgo.ciclo_actual:
                nuevo_ciclo(hallazgo, usuario, "Tratamiento inicial")
            else:
                ciclo_vigente(hallazgo)
        elif accion == "iniciar_analisis":
            requiere_inmediata(ciclo_vigente(hallazgo))
        elif accion == "iniciar_pbi":
            exigir(hallazgo.es_critica == "SI" and hallazgo.origen_tecnologico, "La gestión PBI corresponde a un caso crítico tecnológico.")
            exigir(analisis_completo(ciclo_vigente(hallazgo)), "Finalice el análisis antes de iniciar la gestión PBI.")
        elif accion == "planificar":
            ciclo = ciclo_vigente(hallazgo)
            exigir(hallazgo.es_critica == "SI" and analisis_completo(ciclo), "Finalice el análisis de causa antes del plan de acción.")
            if hallazgo.origen_tecnologico:
                exigir(hallazgo.estado == "PBI_EN_GESTION" and ciclo.pbis.exists(), "Registre la referencia PBI antes de planificar este caso tecnológico.")
        elif accion == "iniciar_implementacion":
            ciclo = ciclo_vigente(hallazgo)
            exigir(analisis_completo(ciclo) and ciclo.acciones.filter(tipo="CORRECTIVA").exists(), "Se necesita análisis finalizado y al menos una acción correctiva.")
        elif accion == "enviar_verificacion":
            if hallazgo.es_critica == "SI":
                exigir(hallazgo.estado == "EN_IMPLEMENTACION", "El caso crítico debe completar análisis y acciones correctivas.")
            tratamiento_completo(hallazgo)
        elif accion == "cerrar":
            ciclo = tratamiento_completo(hallazgo)
            ultima = ciclo.evaluaciones.first()
            exigir(ultima is not None and ultima.resultado == "EFICAZ", "Se requiere la evaluación eficaz del ciclo vigente antes del cierre.")
            ciclo.responsable_cierre = usuario
            ciclo.fecha_cierre = timezone.now()
            ciclo.comentarios_cierre = comentario
            ciclo.resultado_cierre = "EFICAZ"
            ciclo.fecha_fin = timezone.now()
            ciclo.save(update_fields=["fecha_fin", "responsable_cierre", "fecha_cierre", "comentarios_cierre", "resultado_cierre"])
        elif accion == "reabrir":
            nuevo_ciclo(hallazgo, usuario, comentario)
        anterior = hallazgo.estado
        hallazgo.estado = destino
        registrar(hallazgo, usuario, accion.upper(), comentario, anterior=anterior)
        destinatarios = None
        if accion == "enviar":
            destinatarios = set(hallazgo.proceso.validadores.filter(is_active=True).values_list("pk", flat=True)) | {hallazgo.registrado_por_id, hallazgo.responsable_id}
        notificar(hallazgo, accion, f"{etiqueta}. {comentario}".strip(), destinatarios)
        return hallazgo
