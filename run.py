#!/usr/bin/env python3
"""Verifica y ejecuta el Portal NC sobre el esquema Oracle administrado por el DBA.

La aplicación no ejecuta DDL en Oracle. Antes de arrancar comprueba que las 24
tablas, la línea base de migraciones, los catálogos, triggers y permisos DML ya
correspondan exactamente con el código desplegado.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ARCHIVOS_ESTATICOS_REQUERIDOS = (
    "css/portal-v8.css",
    "css/portal.css",
    "images/login-background-claro.png",
)
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def preparar_django() -> None:
    import django

    django.setup()


def verificar() -> None:
    preparar_django()
    verificar_correo()
    from django.core.management import call_command
    from scripts.verificar_oracle_dml import main as verificar_oracle

    verificar_oracle()
    call_command("check", "--deploy")
    print("OK DJANGO: validación de despliegue ejecutada; no hay DDL pendiente.")


def verificar_correo() -> None:
    """Comprueba que el proceso web pueda validar la identidad SSH sin escribir."""

    import paramiko
    from django.conf import settings

    if not settings.CORREO_COMPROMISOS_ENABLED:
        return
    faltantes = [
        nombre
        for nombre, valor in (
            ("CORREO_SSH_HOST", settings.CORREO_SSH_HOST),
            ("CORREO_SSH_USER", settings.CORREO_SSH_USER),
            ("CORREO_SSH_PASSWORD", settings.CORREO_SSH_PASSWORD),
            ("CORREO_REMITENTE_EMAIL", settings.CORREO_REMITENTE_EMAIL),
            ("PORTAL_PUBLIC_URL", settings.PORTAL_PUBLIC_URL),
        )
        if not str(valor).strip()
    ]
    if faltantes:
        raise RuntimeError(
            "Falta configurar el correo corporativo: " + ", ".join(faltantes) + "."
        )

    known_hosts = Path(settings.CORREO_SSH_KNOWN_HOSTS)
    if not known_hosts.is_absolute():
        known_hosts = BASE_DIR / known_hosts
    try:
        if not known_hosts.is_file() or known_hosts.stat().st_size == 0:
            raise FileNotFoundError(str(known_hosts))
        claves = paramiko.HostKeys(str(known_hosts))
    except (OSError, paramiko.SSHException) as error:
        if not known_hosts.exists():
            detalle = "el archivo no existe"
        elif not known_hosts.is_file():
            detalle = "la ruta no es un archivo"
        else:
            try:
                detalle = (
                    "el archivo está vacío"
                    if known_hosts.stat().st_size == 0
                    else "el archivo no puede leerse o no tiene formato known_hosts"
                )
            except OSError:
                detalle = "la cuenta que ejecuta el portal no puede consultar el archivo"
        raise RuntimeError(
            "Falta preparar la identidad SSH del correo: "
            f"{detalle}. Ruta evaluada: {known_hosts}. Ejecute como administrador "
            "scripts\\preparar_identidad_correo_windows.ps1."
        ) from error

    host = settings.CORREO_SSH_HOST
    port = settings.CORREO_SSH_PORT
    nombre_host = host if port == 22 else f"[{host}]:{port}"
    if not claves.lookup(nombre_host):
        raise RuntimeError(
            "El archivo de identidad SSH no corresponde al host de correo "
            f"{nombre_host}. Ruta evaluada: {known_hosts}."
        )
    print(f"OK CORREO: identidad SSH fijada y legible en {known_hosts}.")


def verificar_directorio_estaticos(ruta: Path) -> None:
    """Comprueba antes de collectstatic que la cuenta pueda escribir la ruta."""
    try:
        ruta.mkdir(parents=True, exist_ok=True)
        manifiesto = ruta / "staticfiles.json"
        if manifiesto.exists():
            # En Windows elimina el atributo de solo lectura cuando fue dejado
            # por una copia, antivirus o herramienta de despliegue anterior.
            manifiesto.chmod(manifiesto.stat().st_mode | stat.S_IWRITE)
        prueba = ruta / f".portal-nc-write-{os.getpid()}"
        prueba.write_bytes(b"")
        prueba.unlink()
    except OSError as error:
        raise RuntimeError(
            "La cuenta que inicia el portal no puede escribir en STATIC_ROOT "
            f"({ruta}). Configure STATIC_ROOT con una carpeta propia o conceda "
            "permisos de modificación a esa cuenta."
        ) from error


def comprobar_archivos_estaticos(raiz_estaticos: Path) -> None:
    """Comprueba que la publicación ya contiene los recursos indispensables."""

    faltantes = [
        nombre
        for nombre in ARCHIVOS_ESTATICOS_REQUERIDOS
        if not (raiz_estaticos / Path(nombre)).is_file()
    ]
    manifiesto = raiz_estaticos / "staticfiles.json"
    if not manifiesto.is_file():
        faltantes.append("staticfiles.json")
    if faltantes:
        raise RuntimeError(
            "Faltan archivos estáticos publicados: " + ", ".join(faltantes)
        )


def recolectar_archivos_estaticos() -> None:
    """Genera estáticos durante instalación o inicio manual."""

    from django.conf import settings
    from django.core.management import call_command

    raiz_estaticos = Path(settings.STATIC_ROOT)
    verificar_directorio_estaticos(raiz_estaticos)
    call_command("collectstatic", interactive=False, verbosity=1, clear=False)
    comprobar_archivos_estaticos(raiz_estaticos)
    print(f"OK ESTÁTICOS: recursos preparados en {raiz_estaticos}.")


def preparar_estaticos() -> None:
    preparar_django()
    recolectar_archivos_estaticos()


def iniciar(*, recolectar: bool = True) -> None:
    verificar()
    from django.conf import settings
    from waitress import serve

    raiz_estaticos = Path(settings.STATIC_ROOT)
    if recolectar:
        # El arranque manual conserva la comodidad anterior.
        recolectar_archivos_estaticos()
    else:
        # La tarea programada usa recursos preparados por el publicador y solo
        # necesita lectura. Así no escribe en ProgramData durante el servicio.
        comprobar_archivos_estaticos(raiz_estaticos)
        print(f"OK ESTÁTICOS: recursos publicados disponibles en {raiz_estaticos}.")

    from config.wsgi import application

    host = os.environ.get("PORTAL_BIND_HOST", "0.0.0.0").strip()
    puerto = int(os.environ.get("PORTAL_PORT", "8001"))
    hilos = int(os.environ.get("PORTAL_THREADS", "8"))
    if not (1 <= puerto <= 65535):
        raise RuntimeError("PORTAL_PORT debe estar entre 1 y 65535.")
    if hilos < 4:
        raise RuntimeError("PORTAL_THREADS debe ser al menos 4.")
    print(f"Iniciando Portal NC en {host}:{puerto} con {hilos} hilos.")
    serve(application, host=host, port=puerto, threads=hilos)


def crear_superusuario() -> None:
    verificar()
    from django.core.management import call_command

    call_command("createsuperuser")


def parser() -> argparse.ArgumentParser:
    analizador = argparse.ArgumentParser(description="Operación segura del Portal NC en Oracle")
    sub = analizador.add_subparsers(dest="comando", required=True)
    sub.add_parser("check", help="Comprueba Oracle y Django sin iniciar el portal")
    sub.add_parser("start", help="Comprueba, recolecta estáticos e inicia Waitress")
    sub.add_parser(
        "serve",
        help="Inicia Waitress usando los estáticos preparados por el publicador",
    )
    sub.add_parser("static", help="Recolecta y comprueba los archivos estáticos")
    sub.add_parser("createsuperuser", help="Comprueba el esquema y crea un superusuario")
    return analizador


def main() -> int:
    argumentos = parser().parse_args()
    if argumentos.comando == "check":
        verificar()
    elif argumentos.comando == "start":
        iniciar()
    elif argumentos.comando == "serve":
        iniciar(recolectar=False)
    elif argumentos.comando == "static":
        preparar_estaticos()
    elif argumentos.comando == "createsuperuser":
        crear_superusuario()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Arranque cancelado.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print(f"ERROR DE ARRANQUE: {error}", file=sys.stderr)
        raise SystemExit(1)
