from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    area = models.CharField("área", max_length=150, blank=True)
    cargo = models.CharField(max_length=150, blank=True)
    corporate_identifier = models.CharField(max_length=255, unique=True, null=True, blank=True)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        permissions = [
            ("registrar_hallazgo", "Registrar hallazgos propios"),
            ("validar_hallazgo", "Validar hallazgos de procesos asignados"),
            ("gestionar_tratamiento", "Gestionar tratamiento de procesos asignados"),
            ("evaluar_eficacia", "Evaluar eficacia de procesos asignados"),
            ("cerrar_hallazgo", "Cerrar hallazgos de procesos asignados"),
            ("ver_todos_hallazgos", "Consultar todos los hallazgos"),
            ("administrar_plataforma", "Administrar plataforma y catálogos"),
        ]

    def __str__(self):
        return self.get_full_name() or self.username

    def save(self, *args, **kwargs):
        self.corporate_identifier = self.corporate_identifier or None
        super().save(*args, **kwargs)
