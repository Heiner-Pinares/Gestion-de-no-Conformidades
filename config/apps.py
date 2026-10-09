import re

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.backends.signals import connection_created


_IDENTIFICADOR_ORACLE = re.compile(r"^[A-Z][A-Z0-9_$#]{0,127}$")


def configurar_esquema_oracle(sender, connection, **kwargs):
    """Resuelve nombres no calificados contra USRFACT sin elevar privilegios."""
    if connection.vendor != "oracle":
        return
    esquema = getattr(settings, "DB_SCHEMA", "USRFACT").upper()
    if not _IDENTIFICADOR_ORACLE.fullmatch(esquema):
        raise ImproperlyConfigured("DB_SCHEMA no es un identificador Oracle válido.")
    with connection.cursor() as cursor:
        cursor.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {esquema}")
        if getattr(settings, "DB_REQUIRE_DML_ONLY", False):
            cursor.execute("SELECT privilege FROM session_privs")
            privilegios_sistema = {fila[0] for fila in cursor.fetchall()}
            peligrosos = privilegios_sistema - {"CREATE SESSION"}
            if peligrosos:
                raise ImproperlyConfigured(
                    "La cuenta Oracle del portal tiene privilegios de sistema no permitidos: "
                    + ", ".join(sorted(peligrosos))
                )


class PortalConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "config"
    verbose_name = "Configuración del Portal NC"

    def ready(self):
        connection_created.connect(
            configurar_esquema_oracle,
            dispatch_uid="portal_nc_configurar_esquema_oracle",
        )
