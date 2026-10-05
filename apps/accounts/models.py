from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    # Los roles pertenecen al perfil. Así no se requieren las tablas de grupos
    # y permisos de Django para los tres roles cerrados de este portal.
    groups = None
    user_permissions = None
    roles = models.JSONField(default=list, blank=True)
    area = models.CharField("área", max_length=150, blank=True)
    gerencia = models.CharField(max_length=150, blank=True)
    direccion = models.CharField("dirección", max_length=150, blank=True)
    cargo = models.CharField(max_length=150, blank=True)
    jefe = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="colaboradores",
    )
    corporate_identifier = models.CharField(max_length=255, unique=True, null=True, blank=True)

    class Meta:
        db_table = "usuario"
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        permissions = [
            ("registrar_hallazgo", "Registrar hallazgos propios"),
            ("validar_hallazgo", "Validar hallazgos de procesos asignados"),
            ("gestionar_tratamiento", "Gestionar tratamiento de procesos asignados"),
            ("evaluar_eficacia", "Evaluar eficacia de procesos asignados"),
            ("cerrar_hallazgo", "Dar visto bueno administrativo y cerrar hallazgos"),
            ("ver_todos_hallazgos", "Consultar todos los hallazgos"),
            ("administrar_plataforma", "Administrar plataforma y catálogos"),
        ]

    def __str__(self):
        return self.get_full_name() or self.username

    def save(self, *args, **kwargs):
        self.corporate_identifier = self.corporate_identifier or None
        self.roles = sorted(set(self.roles or []))
        super().save(*args, **kwargs)

    def has_role(self, role):
        return role in (self.roles or [])

    def set_roles(self, roles):
        self.roles = sorted({str(role) for role in roles})
        self.save(update_fields=["roles"])

    def add_role(self, role):
        self.set_roles([*(self.roles or []), role])

    def has_perm(self, perm, obj=None):
        if not self.is_active:
            return False
        if self.is_superuser:
            return True
        codename = perm.rsplit(".", 1)[-1]
        permisos = {
            "USUARIO": {"registrar_hallazgo"},
            "VALIDADOR": {"validar_hallazgo", "gestionar_tratamiento", "evaluar_eficacia"},
            "ADMINISTRADOR": {"administrar_plataforma", "ver_todos_hallazgos", "cerrar_hallazgo"},
        }
        return any(codename in permisos.get(role, set()) for role in (self.roles or []))

    def has_module_perms(self, app_label):
        return self.is_active and (self.is_superuser or bool(self.roles))
