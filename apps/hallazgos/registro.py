"""Proyección de consulta: no duplica registros ni permite editar fuera del workflow."""
from datetime import date, datetime
from django.db import models
from django.utils import timezone

COLUMNAS_REGISTRO = [('numero', 'N°'), ('gerencia', 'Gerencia'), ('proceso', 'Proceso'), ('sub_proceso', 'Sub Proceso'), ('fuente_deteccion', 'Fuente de detección'), ('tipo_hallazgo', 'Tipo de Hallazgo'), ('numero_hallazgo', 'N° Hallazgo'), ('ticket_remedy', 'N° Ticket Remedy (si aplica)'), ('descripcion_hallazgo', 'Descripción del Hallazgo'), ('requisito_referencia', 'Requisito de referencia'), ('responsable_proceso', 'Responsable del proceso'), ('fecha_deteccion', 'Fecha de detección'), ('fecha_registro', 'Fecha de registro'), ('impacto', 'Impacto (si aplica)'), ('urgencia', 'Urgencia (si aplica)'), ('prioridad_criticidad', 'Prioridad / Criticidad (si aplica)'), ('no_conformidad_critica', '¿No conformidad crítica?'), ('causas_raiz', 'Causa(s) raíz identificada(s)'), ('tipo_accion', 'Tipo de Acción'), ('descripcion_accion', 'Descripción de la Acción'), ('responsable', 'Responsable'), ('fet', 'FET'), ('estado', 'Estado'), ('evidencia_implementacion', 'Evidencia de implementación'), ('porcentaje_avance', 'Porcentaje de Avance'), ('comentario', 'Comentario'), ('fecha_evaluacion_eficacia', 'Fecha de evaluación de eficacia'), ('resultado_eficacia', 'Resultado de eficacia'), ('fecha_cierre', 'Fecha de cierre'), ('auditor_verificador', 'Auditor o Verificador'), ('comentarios', 'Comentarios')]

class RegistroGeneral(models.Model):
    fila_id = models.CharField(primary_key=True, max_length=100)
    hallazgo_id = models.BigIntegerField()
    ciclo_id = models.BigIntegerField(null=True)
    accion_id = models.BigIntegerField(null=True)
    numero = models.BigIntegerField(null=True)
    gerencia = models.TextField(null=True)
    proceso = models.TextField(null=True)
    sub_proceso = models.TextField(null=True)
    fuente_deteccion = models.TextField(null=True)
    tipo_hallazgo = models.TextField(null=True)
    numero_hallazgo = models.TextField(null=True)
    ticket_remedy = models.TextField(null=True)
    descripcion_hallazgo = models.TextField(null=True)
    requisito_referencia = models.TextField(null=True)
    responsable_proceso = models.TextField(null=True)
    fecha_deteccion = models.DateTimeField(null=True)
    fecha_registro = models.DateTimeField(null=True)
    impacto = models.TextField(null=True)
    urgencia = models.TextField(null=True)
    prioridad_criticidad = models.TextField(null=True)
    no_conformidad_critica = models.TextField(null=True)
    causas_raiz = models.TextField(null=True)
    tipo_accion = models.TextField(null=True)
    descripcion_accion = models.TextField(null=True)
    responsable = models.TextField(null=True)
    fet = models.DateField(null=True)
    estado = models.TextField(null=True)
    evidencia_implementacion = models.TextField(null=True)
    porcentaje_avance = models.IntegerField(null=True)
    comentario = models.TextField(null=True)
    fecha_evaluacion_eficacia = models.DateField(null=True)
    resultado_eficacia = models.TextField(null=True)
    fecha_cierre = models.DateTimeField(null=True)
    auditor_verificador = models.TextField(null=True)
    comentarios = models.TextField(null=True)

    class Meta:
        managed = False
        db_table = "registro_general"
        ordering = ["numero"]

    def save(self, *args, **kwargs):
        raise TypeError("El registro general es de consulta; use los servicios del portal.")

    def delete(self, *args, **kwargs):
        raise TypeError("El registro general es de consulta.")

    @property
    def valores(self):
        salida = []
        for nombre, _ in COLUMNAS_REGISTRO:
            valor = getattr(self, nombre)
            if isinstance(valor, datetime):
                valor = timezone.localtime(valor).strftime("%d/%m/%Y %H:%M")
            elif isinstance(valor, date):
                valor = valor.strftime("%d/%m/%Y")
            salida.append("" if valor is None else valor)
        return salida
