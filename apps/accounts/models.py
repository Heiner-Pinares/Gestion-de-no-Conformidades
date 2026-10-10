from django.contrib.auth.models import AbstractUser
from django.db import models, router, transaction


ROLES = [
    ("USUARIO", "Usuario"),
    ("VALIDADOR", "Validador"),
    ("ADMINISTRADOR", "Administrador"),
]


class Usuario(AbstractUser):
    # Se conserva el arreglo por compatibilidad con la API actual. La tabla
    # usuario_rol se sincroniza en PostgreSQL y permite consultas relacionales.
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
        db_table = "tbl_usuario_nc"
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
        update_fields = kwargs.get("update_fields")
        sincronizar_roles = self._state.adding or update_fields is None or "roles" in update_fields
        alias = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=alias):
            super().save(*args, **kwargs)
            if sincronizar_roles:
                roles_validos = {codigo for codigo, _ in ROLES}
                roles = sorted(set(self.roles or []) & roles_validos)
                UsuarioRol.objects.using(alias).filter(usuario_id=self.pk).delete()
                UsuarioRol.objects.using(alias).bulk_create(
                    [UsuarioRol(usuario_id=self.pk, rol=rol) for rol in roles]
                )

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


class UsuarioRol(models.Model):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="asignaciones_rol",
    )
    rol = models.CharField(max_length=20, choices=ROLES)

    class Meta:
        db_table = "tbl_usuario_rol_nc"
        ordering = ["usuario_id", "rol"]
        constraints = [
            models.UniqueConstraint(fields=["usuario", "rol"], name="usuario_rol_unico"),
        ]

    def __str__(self):
        return f"{self.usuario}: {self.get_rol_display()}"
