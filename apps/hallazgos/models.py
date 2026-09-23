"""Entidades del proceso, independientes de su interfaz HTTP."""
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .estados import ESTADOS

USER = settings.AUTH_USER_MODEL
SI_NO_NA = [("SI", "Sí"), ("NO", "No"), ("NA", "No aplica")]


def ruta_evidencia(instance, filename):
    return f"evidencias/{instance.hallazgo_id}/{uuid4().hex}{Path(filename).suffix.lower()}"


class CorrelativoSAC(models.Model):
    anio = models.PositiveSmallIntegerField()
    ambito = models.CharField(max_length=10)
    ultimo_numero = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["anio", "ambito"], name="sac_anio_ambito_unico")]


class Hallazgo(models.Model):
    codigo = models.CharField(max_length=40, unique=True, editable=False)
    titulo = models.CharField(max_length=250)
    tipo_registro = models.ForeignKey("catalogos.TipoRegistro", related_name="+", on_delete=models.PROTECT)
    fuente_deteccion = models.ForeignKey("catalogos.FuenteDeteccion", related_name="+", null=True, blank=True, on_delete=models.PROTECT)
    proceso = models.ForeignKey("catalogos.Proceso", on_delete=models.PROTECT)
    subproceso = models.ForeignKey("catalogos.Subproceso", null=True, blank=True, on_delete=models.PROTECT)
    actividad = models.CharField(max_length=250, blank=True)
    descripcion = models.TextField(blank=True)
    ticket_remedy = models.CharField(max_length=120, blank=True)
    responsable = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="hallazgos_responsable")
    registrado_por = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="hallazgos_registrados")
    fecha_deteccion = models.DateTimeField(null=True, blank=True)
    fecha_registro = models.DateTimeField(default=timezone.now, editable=False)
    fecha_solucion = models.DateField(null=True, blank=True)
    impacto_clientes = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(3)])
    impacto_tiempo = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(3)])
    impacto_soles = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(3)])
    impacto_resultante = models.PositiveSmallIntegerField(null=True, blank=True, editable=False)
    urgencia = models.ForeignKey("catalogos.Urgencia", related_name="+", null=True, blank=True, on_delete=models.PROTECT)
    prioridad = models.ForeignKey("catalogos.Prioridad", related_name="+", null=True, blank=True, on_delete=models.PROTECT, editable=False)
    prioridad_snapshot = models.CharField(max_length=180, blank=True, editable=False)
    aplica_impacto = models.BooleanField(default=True)
    justificacion_no_impacto = models.TextField(blank=True)
    es_critica = models.CharField(max_length=2, choices=SI_NO_NA, blank=True)
    origen_tecnologico = models.BooleanField(default=False)
    criterio_categoria = models.TextField(blank=True)
    requisito_referencia = models.TextField(blank=True)
    estado = models.CharField(max_length=30, choices=ESTADOS, default="BORRADOR")
    version = models.PositiveIntegerField(default=1, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(USER, null=True, on_delete=models.PROTECT, related_name="hallazgos_actualizados")

    class Meta:
        ordering = ["-fecha_registro", "-pk"]
        indexes = [models.Index(fields=["estado", "fecha_registro"]), models.Index(fields=["responsable", "estado"]), models.Index(fields=["proceso", "fecha_solucion"])]
        constraints = [
            models.CheckConstraint(condition=Q(impacto_clientes__isnull=True) | Q(impacto_clientes__range=(1, 3)), name="impacto_clientes_rango"),
            models.CheckConstraint(condition=Q(impacto_tiempo__isnull=True) | Q(impacto_tiempo__range=(1, 3)), name="impacto_tiempo_rango"),
            models.CheckConstraint(condition=Q(impacto_soles__isnull=True) | Q(impacto_soles__range=(1, 3)), name="impacto_soles_rango"),
            models.CheckConstraint(condition=Q(impacto_resultante__isnull=True) | Q(impacto_resultante__range=(1, 3)), name="impacto_resultante_rango"),
            models.CheckConstraint(condition=Q(es_critica__in=["SI", "NO", "NA", ""]), name="hallazgo_criticidad_valida"),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        for field, clase in [("tipo_registro", "TIPO"), ("fuente_deteccion", "FUENTE"), ("urgencia", "URGENCIA"), ("prioridad", "PRIORIDAD")]:
            if getattr(self, field + "_id") and getattr(self, field).clase != clase:
                raise ValidationError({field: "El valor pertenece a otro catálogo."})

    @property
    def ciclo_actual(self):
        return self.ciclos.order_by("-numero").first()

    def __str__(self):
        return self.codigo


class CicloTratamiento(models.Model):
    hallazgo = models.ForeignKey(Hallazgo, on_delete=models.PROTECT, related_name="ciclos")
    numero = models.PositiveIntegerField()
    motivo = models.TextField()
    creado_por = models.ForeignKey(USER, on_delete=models.PROTECT)
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    analisis_responsable = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="analisis_asignados")
    analisis_inicio = models.DateTimeField(null=True, blank=True)
    analisis_fin = models.DateTimeField(null=True, blank=True)
    causa_raiz = models.TextField(blank=True)
    checklist_snapshot = models.JSONField(default=list, blank=True)
    respuestas = models.JSONField(default=list, blank=True)
    control = models.JSONField(default=dict, blank=True)
    responsable_cierre = models.ForeignKey(USER, null=True, blank=True, on_delete=models.PROTECT, related_name="cierres_realizados")
    fecha_cierre = models.DateTimeField(null=True, blank=True)
    comentarios_cierre = models.TextField(blank=True)
    resultado_cierre = models.CharField(max_length=12, blank=True)


    class Meta:
        ordering = ["numero"]
        constraints = [models.UniqueConstraint(fields=["hallazgo", "numero"], name="ciclo_hallazgo_numero_unico")]

    def __str__(self):
        return f"{self.hallazgo.codigo} · Ciclo {self.numero}"


class Accion(models.Model):
    TIPOS = [("INMEDIATA", "Acción inmediata"), ("CORRECTIVA", "Acción correctiva")]
    ESTADOS = [("PENDIENTE", "Pendiente"), ("EN_PROCESO", "En proceso"), ("COMPLETADA", "Completada")]
    ciclo = models.ForeignKey(CicloTratamiento, on_delete=models.PROTECT, related_name="acciones")
    codigo = models.CharField(max_length=50, unique=True, editable=False)
    tipo = models.CharField(max_length=12, choices=TIPOS)
    descripcion = models.TextField()
    responsable = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="acciones_asignadas")
    fecha_inicio = models.DateField()
    fet_inicial = models.DateField()
    fecha_vigente = models.DateField()
    fecha_real = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=12, choices=ESTADOS, default="PENDIENTE")
    porcentaje_avance = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    resultado_esperado = models.TextField()
    comentario = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(condition=Q(porcentaje_avance__lte=100), name="accion_avance_max_100"),
            models.CheckConstraint(condition=Q(fet_inicial__gte=F("fecha_inicio")), name="accion_fet_desde_inicio"),
            models.CheckConstraint(condition=Q(fecha_vigente__gte=F("fecha_inicio")), name="accion_vigente_desde_inicio"),
            models.CheckConstraint(condition=Q(fecha_real__isnull=True) | Q(fecha_real__gte=F("fecha_inicio")), name="accion_real_desde_inicio"),
            models.CheckConstraint(condition=Q(tipo__in=["INMEDIATA", "CORRECTIVA"]), name="accion_tipo_valido"),
            models.CheckConstraint(condition=Q(estado__in=["PENDIENTE", "EN_PROCESO", "COMPLETADA"]), name="accion_estado_valido"),
            models.CheckConstraint(condition=(Q(estado="COMPLETADA", porcentaje_avance=100, fecha_real__isnull=False) | (~Q(estado="COMPLETADA") & Q(porcentaje_avance__lt=100, fecha_real__isnull=True))), name="accion_completada_coherente"),
        ]

    @property
    def hallazgo(self):
        return self.ciclo.hallazgo

    @property
    def reprogramaciones(self):
        return self.eventos.filter(accion="REPROGRAMACION").order_by("fecha_hora", "pk")

    @property
    def seguimientos(self):
        return self.eventos.filter(accion="SEGUIMIENTO_ACCION")

    @property
    def eficiencia(self):
        """Indicador demo de cumplimiento, diferente de la eficacia del tratamiento."""
        return max(0, 100 - 20 * self.reprogramaciones.count())

    def __str__(self):
        return self.codigo


class PBI(models.Model):
    ciclo = models.ForeignKey(CicloTratamiento, on_delete=models.PROTECT, related_name="pbis")
    numero_pbi = models.CharField(max_length=100)
    ticket_incidente = models.CharField(max_length=100, blank=True)
    sistema = models.CharField(max_length=200)
    herramienta = models.CharField(max_length=100, default="Helix (registro manual)")
    responsable_ti = models.ForeignKey(USER, on_delete=models.PROTECT)
    estado = models.CharField(max_length=10, choices=[("ABIERTO", "Abierto"), ("CERRADO", "Cerrado")], default="ABIERTO")
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_cierre = models.DateField(null=True, blank=True)
    observacion = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["ciclo", "numero_pbi"], name="pbi_referencia_ciclo_unico"), models.CheckConstraint(condition=Q(estado="ABIERTO", fecha_cierre__isnull=True) | Q(estado="CERRADO", fecha_cierre__isnull=False), name="pbi_cierre_coherente")]


class EvaluacionEficacia(models.Model):
    RESULTADOS = [("EFICAZ", "Eficaz"), ("NO_EFICAZ", "No eficaz")]
    ciclo = models.ForeignKey(CicloTratamiento, on_delete=models.PROTECT, related_name="evaluaciones")
    evaluador = models.ForeignKey(USER, on_delete=models.PROTECT)
    fecha_evaluacion = models.DateField()
    resultado = models.CharField(max_length=12, choices=RESULTADOS)
    comentario = models.TextField()
    fecha_registro = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-fecha_registro", "-pk"]
        constraints = [models.CheckConstraint(condition=Q(resultado__in=["EFICAZ", "NO_EFICAZ"]), name="eficacia_resultado_valido")]


class ComunicacionHallazgo(models.Model):
    ciclo = models.ForeignKey(CicloTratamiento, on_delete=models.PROTECT, related_name="comunicaciones")
    registrado_por = models.ForeignKey(USER, on_delete=models.PROTECT)
    destinatarios = models.CharField(max_length=500)
    medio = models.CharField(max_length=120)
    descripcion = models.TextField()
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-fecha"]


class Evidencia(models.Model):
    hallazgo = models.ForeignKey(Hallazgo, on_delete=models.PROTECT, related_name="evidencias")
    accion = models.ForeignKey(Accion, on_delete=models.PROTECT, null=True, blank=True, related_name="evidencias")
    analisis = models.ForeignKey(CicloTratamiento, related_name="evidencias_analisis", on_delete=models.PROTECT, null=True, blank=True)
    evaluacion = models.ForeignKey(EvaluacionEficacia, on_delete=models.PROTECT, null=True, blank=True, related_name="evidencias")
    cierre = models.ForeignKey(CicloTratamiento, related_name="evidencias_cierre", on_delete=models.PROTECT, null=True, blank=True)
    archivo = models.FileField(upload_to=ruta_evidencia)
    nombre_original = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    tamanio = models.PositiveIntegerField()
    subido_por = models.ForeignKey(USER, on_delete=models.PROTECT)
    fecha_carga = models.DateTimeField(default=timezone.now)
    descripcion = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha_carga"]
        constraints = [models.CheckConstraint(condition=(Q(accion__isnull=True, analisis__isnull=True, evaluacion__isnull=True) | Q(accion__isnull=True, analisis__isnull=True, cierre__isnull=True) | Q(accion__isnull=True, evaluacion__isnull=True, cierre__isnull=True) | Q(analisis__isnull=True, evaluacion__isnull=True, cierre__isnull=True)), name="evidencia_un_contexto_maximo")]


class HistorialHallazgo(models.Model):
    accion_relacionada = models.ForeignKey(Accion, null=True, blank=True, on_delete=models.PROTECT, related_name="eventos")
    hallazgo = models.ForeignKey(Hallazgo, on_delete=models.PROTECT, related_name="historial")
    usuario = models.ForeignKey(USER, on_delete=models.PROTECT)
    fecha_hora = models.DateTimeField(default=timezone.now)
    accion = models.CharField(max_length=70)
    estado_anterior = models.CharField(max_length=30, blank=True)
    estado_nuevo = models.CharField(max_length=30, blank=True)
    comentario = models.TextField(blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-fecha_hora", "-pk"]


class Notificacion(models.Model):
    usuario = models.ForeignKey(USER, on_delete=models.PROTECT, related_name="notificaciones")
    hallazgo = models.ForeignKey(Hallazgo, on_delete=models.PROTECT, related_name="notificaciones")
    tipo = models.CharField(max_length=50)
    titulo = models.CharField(max_length=250)
    mensaje = models.TextField()
    leida = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_lectura = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha_creacion"]
        indexes = [models.Index(fields=["usuario", "leida", "fecha_creacion"])]


from .registro import RegistroGeneral  # Modelo de la vista SQL de consulta.
