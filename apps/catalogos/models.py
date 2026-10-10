from django.conf import settings
from django.db import models, router, transaction

class Maestro(models.Model):
    nombre = models.CharField(max_length=180)
    activo = models.BooleanField(default=True)

    class Meta:
        abstract = True
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Catalogo(models.Model):
    REGISTRO_TIPO = "CATALOGO"
    CLASES = [(c, n) for c, n in [("TIPO", "Tipo de hallazgo"), ("FUENTE", "Fuente"), ("IMPACTO", "Impacto"), ("URGENCIA", "Urgencia"), ("PRIORIDAD", "Prioridad"), ("CATEGORIA", "Categoría 6M")]]
    id = models.BigAutoField(primary_key=True)
    clase = models.CharField(max_length=12, choices=CLASES)
    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=180)
    activo = models.BooleanField(default=True)
    valor = models.PositiveSmallIntegerField(null=True, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "tbl_catalogo_nc"
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["clase", "codigo"], name="catalogo_clase_codigo_unico"),
            models.UniqueConstraint(fields=["clase", "valor"], condition=models.Q(valor__isnull=False), name="catalogo_clase_valor_unico"),
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


class ValidadorRelation:
    """API mínima de relación para conservar los usos actuales del portal."""
    def __init__(self, proceso):
        self.proceso = proceso

    def all(self):
        from apps.accounts.models import Usuario
        return Usuario.objects.filter(
            pk__in=ProcesoValidador.objects.filter(
                proceso_id=self.proceso.pk,
            ).values("usuario_id"),
        )

    def filter(self, *args, **kwargs):
        return self.all().filter(*args, **kwargs)

    def values_list(self, *args, **kwargs):
        return self.all().values_list(*args, **kwargs)

    def exists(self):
        return self.all().exists()

    def add(self, *usuarios):
        ids = set(self.proceso.validadores_ids or [])
        ids.update(u.pk if hasattr(u, "pk") else int(u) for u in usuarios)
        self.proceso.validadores_ids = sorted(ids)
        self.proceso.save(update_fields=["validadores_ids"])

    def set(self, usuarios):
        self.proceso.validadores_ids = sorted({u.pk if hasattr(u, "pk") else int(u) for u in usuarios})
        self.proceso.save(update_fields=["validadores_ids"])


class Proceso(Maestro):
    REGISTRO_TIPO = "PROCESO"
    id = models.BigAutoField(primary_key=True)
    gerencia = models.CharField(max_length=180, blank=True)
    nombre = models.CharField(max_length=180)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="procesos_responsables")
    validadores_ids = models.JSONField(default=list, blank=True)
    activo = models.BooleanField(default=True)

    class Meta(Maestro.Meta):
        db_table = "tbl_proceso_nc"
        ordering = ["nombre"]
        constraints = [models.UniqueConstraint(fields=["nombre"], name="proceso_nombre_unico")]

    @property
    def validadores(self):
        return ValidadorRelation(self)

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.validadores_ids = sorted({int(pk) for pk in (self.validadores_ids or [])})
        update_fields = kwargs.get("update_fields")
        sincronizar_validadores = (
            self._state.adding
            or update_fields is None
            or "validadores_ids" in update_fields
        )
        alias = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=alias):
            super().save(*args, **kwargs)
            if sincronizar_validadores:
                modelo_usuario = self._meta.get_field("responsable").remote_field.model
                ids_existentes = set(
                    modelo_usuario.objects.using(alias)
                    .filter(pk__in=self.validadores_ids)
                    .values_list("pk", flat=True)
                )
                ProcesoValidador.objects.using(alias).filter(proceso_id=self.pk).delete()
                ProcesoValidador.objects.using(alias).bulk_create(
                    [
                        ProcesoValidador(proceso_id=self.pk, usuario_id=usuario_id)
                        for usuario_id in sorted(ids_existentes)
                    ]
                )


class ProcesoValidador(models.Model):
    proceso = models.ForeignKey(
        Proceso,
        on_delete=models.CASCADE,
        related_name="asignaciones_validacion",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="asignaciones_proceso",
    )

    class Meta:
        db_table = "tbl_proceso_validador_nc"
        ordering = ["proceso_id", "usuario_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["proceso", "usuario"],
                name="proceso_validador_unico",
            ),
        ]

    def __str__(self):
        return f"{self.proceso}: {self.usuario}"


class Subproceso(Maestro):
    REGISTRO_TIPO = "SUBPROCESO"
    id = models.BigAutoField(primary_key=True)
    proceso = models.ForeignKey(Proceso, on_delete=models.PROTECT, related_name="subprocesos")
    nombre = models.CharField(max_length=180)
    activo = models.BooleanField(default=True)

    class Meta(Maestro.Meta):
        db_table = "tbl_subproceso_nc"
        ordering = ["nombre"]
        constraints = [models.UniqueConstraint(fields=["proceso", "nombre"], name="subproceso_proceso_nombre_unico")]

    def __str__(self):
        return self.nombre


class MatrizPrioridad(models.Model):
    REGISTRO_TIPO = "MATRIZ_PRIORIDAD"
    id = models.BigAutoField(primary_key=True)
    impacto = models.ForeignKey(Impacto, related_name="+", on_delete=models.PROTECT)
    urgencia = models.ForeignKey(Urgencia, related_name="+", on_delete=models.PROTECT)
    prioridad = models.ForeignKey(Prioridad, related_name="+", on_delete=models.PROTECT)
    activo = models.BooleanField(default=True)
    es_demo = models.BooleanField(default=True)

    class Meta:
        db_table = "tbl_matriz_prioridad_nc"
        ordering = ["impacto_id", "urgencia_id"]
        constraints = [models.UniqueConstraint(fields=["impacto", "urgencia"], name="matriz_prioridad_combinacion_unica")]

    def clean(self):
        from django.core.exceptions import ValidationError
        for field, clase in [("impacto", "IMPACTO"), ("urgencia", "URGENCIA"), ("prioridad", "PRIORIDAD")]:
            if getattr(self, field + "_id") and getattr(self, field).clase != clase:
                raise ValidationError({field: "Seleccione un valor del catálogo correcto."})

    def __str__(self):
        return f"{self.impacto} / {self.urgencia}: {self.prioridad}"


class ConfiguracionImpacto(models.Model):
    REGISTRO_TIPO = "CONFIGURACION_IMPACTO"
    id = models.BigAutoField(primary_key=True)
    predeterminada = models.BooleanField(default=True)
    clientes_bajo_desde = models.PositiveBigIntegerField(default=0)
    clientes_bajo_hasta = models.PositiveBigIntegerField(default=99)
    clientes_medio_desde = models.PositiveBigIntegerField(default=100)
    clientes_medio_hasta = models.PositiveBigIntegerField(default=499)
    clientes_alto_desde = models.PositiveBigIntegerField(default=500)
    tiempo_bajo_desde = models.PositiveIntegerField(default=0)
    tiempo_bajo_hasta = models.PositiveIntegerField(default=29)
    tiempo_medio_desde = models.PositiveIntegerField(default=30)
    tiempo_medio_hasta = models.PositiveIntegerField(default=120)
    tiempo_alto_desde = models.PositiveIntegerField(default=121)
    financiero_bajo_desde = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    financiero_bajo_hasta = models.DecimalField(max_digits=14, decimal_places=0, default=999999)
    financiero_medio_desde = models.DecimalField(max_digits=14, decimal_places=0, default=1000000)
    financiero_medio_hasta = models.DecimalField(max_digits=14, decimal_places=0, default=1999999)
    financiero_alto_desde = models.DecimalField(max_digits=14, decimal_places=0, default=2000000)

    class Meta:
        db_table = "tbl_configuracion_impacto_nc"
        verbose_name = "configuración de impacto"
        verbose_name_plural = "configuración de impacto"

    def __str__(self):
        return "Rangos predeterminados de evaluación de impacto"

    @staticmethod
    def numero(valor):
        return f"{int(valor):,}"

    @property
    def rangos_usuario(self):
        n = self.numero
        return {
            "clientes": {"bajo": f"{n(self.clientes_bajo_desde)} – {n(self.clientes_bajo_hasta)} cuentas", "medio": f"{n(self.clientes_medio_desde)} – {n(self.clientes_medio_hasta)} cuentas", "alto": f"{n(self.clientes_alto_desde)} o más cuentas"},
            "tiempo": {"bajo": f"{n(self.tiempo_bajo_desde)} – {n(self.tiempo_bajo_hasta)} min", "medio": f"{n(self.tiempo_medio_desde)} – {n(self.tiempo_medio_hasta)} min", "alto": f"{n(self.tiempo_alto_desde)} o más min"},
            "financiero": {"bajo": f"Menos de S/ {n(self.financiero_medio_desde)}", "medio": f"S/ {n(self.financiero_medio_desde)} a menos de S/ {n(self.financiero_alto_desde)}", "alto": f"S/ {n(self.financiero_alto_desde)} o más"},
        }


class ConfiguracionUrgencia(models.Model):
    """Rangos de urgencia por jefatura en la tabla física configuración."""
    REGISTRO_TIPO = "CONFIGURACION_URGENCIA"
    AREAS = (("FACTURACION", "Facturación"), ("POST_FACTURACION", "Post facturación"))
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=30, choices=AREAS)
    nombre = models.CharField(max_length=180)
    activo = models.BooleanField(default=True)
    bajo_desde = models.PositiveIntegerField(default=0, db_column="tiempo_bajo_desde")
    bajo_hasta = models.PositiveIntegerField(default=27, db_column="tiempo_bajo_hasta")
    medio_desde = models.PositiveIntegerField(default=28, db_column="tiempo_medio_desde")
    medio_hasta = models.PositiveIntegerField(default=32, db_column="tiempo_medio_hasta")
    alto_desde = models.PositiveIntegerField(default=33, db_column="tiempo_alto_desde")

    class Meta:
        db_table = "tbl_configuracion_urgencia_nc"
        ordering = ["codigo"]

    def __str__(self):
        return self.get_codigo_display()

    @staticmethod
    def codigo_para_area(area):
        from django.utils.text import slugify
        normalizada = slugify(area or "").replace("-", "_")
        if "post_facturacion" in normalizada or ("post" in normalizada and "facturacion" in normalizada):
            return "POST_FACTURACION"
        if "facturacion" in normalizada:
            return "FACTURACION"
        return None

    @property
    def rangos_usuario(self):
        return {
            "bajo": f"Menos de {self.medio_desde} h",
            "medio": f"De {self.medio_desde} a {self.medio_hasta} h",
            "alto": f"Más de {self.medio_hasta} h",
        }

    def seleccion_para(self, nivel):
        return self.rangos_usuario.get({1: "bajo", 2: "medio", 3: "alto"}.get(nivel), "")


class PreguntaCausa(models.Model):
    REGISTRO_TIPO = "PREGUNTA_CAUSA"
    codigo = models.CharField(primary_key=True, max_length=30)
    categoria = models.ForeignKey(CategoriaCausa, on_delete=models.PROTECT, related_name="preguntas")
    texto = models.TextField()
    orden = models.PositiveSmallIntegerField()
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "tbl_pregunta_causa_nc"
        ordering = ["categoria__orden", "orden"]

    def __str__(self):
        return f"{self.codigo} · {self.texto}"


class AuditoriaAdministracion(models.Model):
    REGISTRO_TIPO = "AUDITORIA_ADMINISTRACION"
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)
    entidad = models.CharField(max_length=100)
    objeto = models.CharField(max_length=100)
    accion = models.CharField(max_length=70)
    antes = models.JSONField(default=dict)
    despues = models.JSONField(default=dict)

    class Meta:
        db_table = "tbl_auditoria_administracion_nc"
        ordering = ["-fecha", "-pk"]
