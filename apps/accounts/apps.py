from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        from django.db.migrations.recorder import MigrationRecorder
        # La tabla de sesiones también sigue la nomenclatura oficial del portal.
        from django.contrib.sessions.models import Session
        MigrationRecorder.Migration._meta.db_table = "tbl_django_migrations_nc"
        Session._meta.db_table = "tbl_django_session_nc"

        # Los roles propios no requieren las tablas genéricas de permisos/content-types.
        from django.contrib.auth.management import create_permissions
        from django.contrib.contenttypes.management import create_contenttypes
        post_migrate.disconnect(
            create_permissions,
            dispatch_uid="django.contrib.auth.management.create_permissions",
        )
        post_migrate.disconnect(create_contenttypes)
