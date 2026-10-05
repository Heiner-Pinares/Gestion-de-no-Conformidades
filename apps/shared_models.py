"""Utilidades para modelos lógicos que comparten una tabla física tipada."""
from django.db import models


class TypedManager(models.Manager):
    """Aísla automáticamente las filas del tipo lógico del modelo."""

    def get_queryset(self):
        return super().get_queryset().filter(registro_tipo=self.model.REGISTRO_TIPO)

    def create(self, **kwargs):
        kwargs["registro_tipo"] = self.model.REGISTRO_TIPO
        return super().create(**kwargs)

    def bulk_create(self, objs, **kwargs):
        for obj in objs:
            obj.registro_tipo = self.model.REGISTRO_TIPO
        return super().bulk_create(objs, **kwargs)


class TypedSharedModel(models.Model):
    """Base común; cada submodelo sigue ofreciendo una API ORM normal."""

    REGISTRO_TIPO = ""
    registro_tipo = models.CharField(max_length=40, editable=False)
    objects = TypedManager()

    class Meta:
        abstract = True
        managed = False
        base_manager_name = "objects"
        default_manager_name = "objects"

    def save(self, *args, **kwargs):
        self.registro_tipo = self.REGISTRO_TIPO
        return super().save(*args, **kwargs)
