from django.conf import settings
from django.db import models


class Maestro(models.Model):
    nombre = models.CharField(max_length=180)
    activo = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Catalogo(models.Model):
    CLASES = [(c, n) for c, n in [("TIPO", "Tipo de hallazgo"), ("FUENTE", "Fuente"), ("IMPACTO", "Impacto"), ("URGENCIA", "Urgencia"), ("PRIORIDAD", "Prioridad"), ("CATEGORIA", "Categoría 6M")]]
    clase = models.CharField(max_length=12, choices=CLASES)
    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=180)
    activo = models.BooleanField(default=True)
    valor = models.PositiveSmallIntegerField(null=True, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["clase", "codigo"], name="catalogo_clase_codigo_unico"),
            models.UniqueConstraint(fields=["clase", "valor"], name="catalogo_clase_valor_unico"),
            models.CheckConstraint(condition=(~models.Q(clase__in=["IMPACTO", "URGENCIA"]) | models.Q(valor__range=(1, 3), valor__isnull=False)), name="catalogo_nivel_valido"),
        ]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        if getattr(self, "CLASE", None):
            self.clase = self.CLASE
        if self.clase in {"IMPACTO", "URGENCIA"} and self.valor is not None:
            self.codigo = str(self.valor)
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        expected = getattr(self, "CLASE", None)
        if expected and self.clase != expected:
            raise ValidationError("El valor pertenece a otro catálogo.")


class CatalogoManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(clase=self.model.CLASE)


class CatalogoTipado:

    def __init__(self, *args, **kwargs):
        if not args:
            kwargs.setdefault("clase", self.CLASE)
            if self.CLASE in {"IMPACTO", "URGENCIA"} and "valor" in kwargs:
                kwargs.setdefault("codigo", str(kwargs["valor"]))
        super().__init__(*args, **kwargs)


class TipoRegistro(CatalogoTipado, Catalogo):
    objects = CatalogoManager()
    CLASE = "TIPO"
    class Meta:
        proxy = True


class FuenteDeteccion(CatalogoTipado, Catalogo):
    objects = CatalogoManager()
    CLASE = "FUENTE"
    class Meta:
        proxy = True


class Impacto(CatalogoTipado, Catalogo):
    objects = CatalogoManager()
    CLASE = "IMPACTO"
    class Meta:
        proxy = True


class Urgencia(CatalogoTipado, Catalogo):
    objects = CatalogoManager()
    CLASE = "URGENCIA"
    class Meta:
        proxy = True


class Prioridad(CatalogoTipado, Catalogo):
    objects = CatalogoManager()
    CLASE = "PRIORIDAD"
    class Meta:
        proxy = True


class CategoriaCausa(CatalogoTipado, Catalogo):
    objects = CatalogoManager()
    CLASE = "CATEGORIA"
    class Meta:
        proxy = True


class Proceso(Maestro):
    gerencia = models.CharField(max_length=180, blank=True)
    nombre = models.CharField(max_length=180, unique=True)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="procesos_responsables")
    validadores = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="procesos_validacion")


class Subproceso(Maestro):
    proceso = models.ForeignKey(Proceso, on_delete=models.PROTECT, related_name="subprocesos")

    class Meta(Maestro.Meta):
        constraints = [models.UniqueConstraint(fields=["proceso", "nombre"], name="subproceso_nombre_unico")]


class MatrizPrioridad(models.Model):
    impacto = models.ForeignKey(Impacto, related_name="+", on_delete=models.PROTECT)
    urgencia = models.ForeignKey(Urgencia, related_name="+", on_delete=models.PROTECT)
    prioridad = models.ForeignKey(Prioridad, related_name="+", on_delete=models.PROTECT)
    activo = models.BooleanField(default=True)
    es_demo = models.BooleanField(default=True)

    class Meta:
        ordering = ["impacto_id", "urgencia_id"]
        constraints = [models.UniqueConstraint(fields=["impacto", "urgencia"], name="matriz_prioridad_combinacion_unica")]

    def clean(self):
        from django.core.exceptions import ValidationError
        for field, clase in [("impacto", "IMPACTO"), ("urgencia", "URGENCIA"), ("prioridad", "PRIORIDAD")]:
            if getattr(self, field + "_id") and getattr(self, field).clase != clase:
                raise ValidationError({field: "Seleccione un valor del catálogo correcto."})

    def __str__(self):
        return f"{self.impacto} / {self.urgencia}: {self.prioridad}"


class PreguntaCausa(models.Model):
    codigo = models.CharField(primary_key=True, max_length=8)
    categoria = models.ForeignKey(CategoriaCausa, on_delete=models.PROTECT, related_name="preguntas")
    texto = models.TextField()
    orden = models.PositiveSmallIntegerField()
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["categoria__orden", "orden"]

    def __str__(self):
        return f"{self.codigo} · {self.texto}"


class AuditoriaAdministracion(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    entidad = models.CharField(max_length=100)
    objeto = models.CharField(max_length=100)
    accion = models.CharField(max_length=40)
    antes = models.JSONField(default=dict)
    despues = models.JSONField(default=dict)

    class Meta:
        ordering = ["-fecha", "-pk"]
