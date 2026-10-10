"""Configuración del portal para PostgreSQL local u Oracle en producción."""
from pathlib import Path
import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env(DEBUG=(bool, False))
# Los secretos locales tienen prioridad y nunca deben versionarse.
local_env = BASE_DIR / ".env.local"
if local_env.exists():
    environ.Env.read_env(local_env)
environ.Env.read_env(BASE_DIR / ".env")


def secreto(nombre: str, archivo_nombre: str, *, default: str | None = None) -> str:
    """Obtiene un secreto desde archivo o entorno sin exponer su contenido."""
    archivo = env(archivo_nombre, default="").strip()
    if archivo:
        ruta = Path(archivo)
        if not ruta.is_absolute():
            ruta = BASE_DIR / ruta
        try:
            valor = ruta.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as error:
            raise ImproperlyConfigured(
                f"No se pudo leer el archivo configurado en {archivo_nombre}."
            ) from error
        if not valor:
            raise ImproperlyConfigured(f"El archivo configurado en {archivo_nombre} está vacío.")
        return valor
    valor = env(nombre, default=default)
    if valor is None or (default is None and not str(valor)):
        raise ImproperlyConfigured(
            f"Falta {nombre}. Defina {nombre} o, preferentemente, {archivo_nombre}."
        )
    return str(valor)


SECRET_KEY = secreto("SECRET_KEY", "SECRET_KEY_FILE")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
INSTALLED_APPS = [
    "config.apps.PortalConfig",
    "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "apps.accounts", "apps.catalogos", "apps.hallazgos",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "apps.accounts.context_processors.perfil",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DB_ENGINE = env("DB_ENGINE", default="postgresql").strip().lower()
if DB_ENGINE in {"postgres", "postgresql"}:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql", "NAME": env("DB_NAME"),
        "USER": env("DB_USER"), "PASSWORD": secreto("DB_PASSWORD", "DB_PASSWORD_FILE"),
        "HOST": env("DB_HOST", default="127.0.0.1"), "PORT": env("DB_PORT", default="5432"),
        "CONN_MAX_AGE": 60, "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": 5},
    }}
elif DB_ENGINE == "oracle":
    DB_SCHEMA = env("DB_SCHEMA", default="USRFACT").strip().upper()
    # Se conserva exactamente el usuario recibido para conectarse. La versión
    # normalizada solo se usa en las validaciones de seguridad.
    DB_USER = env("DB_USER").strip()
    DB_USER_NORMALIZADO = DB_USER.upper()
    DB_REQUIRE_DML_ONLY = env.bool("DB_REQUIRE_DML_ONLY", default=True)
    DB_ALLOWED_USERS = {
        usuario.strip().upper()
        for usuario in env.list(
            "DB_ALLOWED_USERS",
            default=["USRFACSOP"],
        )
        if usuario.strip()
    }
    if DB_SCHEMA != "USRFACT":
        raise ImproperlyConfigured("DB_SCHEMA debe ser USRFACT para este paquete de base de datos.")
    if DB_REQUIRE_DML_ONLY and DB_USER_NORMALIZADO == DB_SCHEMA:
        raise ImproperlyConfigured(
            "El portal no puede conectarse como USRFACT. Use una cuenta con permisos DML."
        )
    if DB_REQUIRE_DML_ONLY and DB_ALLOWED_USERS and DB_USER_NORMALIZADO not in DB_ALLOWED_USERS:
        raise ImproperlyConfigured(
            "DB_USER debe ser una cuenta DML autorizada: " + ", ".join(sorted(DB_ALLOWED_USERS))
        )
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.oracle",
        "NAME": env("DB_DSN"),
        "USER": DB_USER,
        "PASSWORD": secreto("DB_PASSWORD", "DB_PASSWORD_FILE"),
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
        "CONN_HEALTH_CHECKS": True,
    }}
else:
    raise ImproperlyConfigured("DB_ENGINE debe ser postgresql u oracle.")
AUTH_USER_MODEL = "accounts.Usuario"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
# Durante pruebas y despliegues graduales permite resolver desde STATICFILES_DIRS;
# run.py siempre ejecuta collectstatic antes de abrir el puerto de producción.
WHITENOISE_MANIFEST_STRICT = False
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))
MEDIA_URL = "/evidencias-privadas/"  # Nunca publicada como directorio estático.
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
MAX_EVIDENCE_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# Las sesiones quedan dentro del mismo esquema de 24 tablas.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 8 * 60 * 60
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=not DEBUG)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=False)
if env.bool("TRUST_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SAC_SEQUENCE_SCOPE = env("SAC_SEQUENCE_SCOPE", default="TYPE")
REQUIRE_CLOSED_PBI = env.bool("REQUIRE_CLOSED_PBI", default=False)
ENABLE_DEMO_DATA = env.bool("ENABLE_DEMO_DATA", default=False)
MICROSOFT_SSO_ENABLED = env.bool("MICROSOFT_SSO_ENABLED", default=False)
MICROSOFT_TENANT_ID = env("MICROSOFT_TENANT_ID", default="")
MICROSOFT_CLIENT_ID = env("MICROSOFT_CLIENT_ID", default="")
MICROSOFT_CLIENT_SECRET = secreto(
    "MICROSOFT_CLIENT_SECRET",
    "MICROSOFT_CLIENT_SECRET_FILE",
    default="",
)
MICROSOFT_REDIRECT_URI = env("MICROSOFT_REDIRECT_URI", default="")
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "formatters": {"standard": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "standard"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}
