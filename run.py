#!/usr/bin/env python3
"""Verifica y ejecuta el Portal NC sobre el esquema Oracle administrado por el DBA.

La aplicación no ejecuta DDL en Oracle. Antes de arrancar comprueba que las 24
tablas, la línea base de migraciones, los catálogos, triggers y permisos DML ya
correspondan exactamente con el código desplegado.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def preparar_django() -> None:
    import django

    django.setup()


def verificar() -> None:
    preparar_django()
    from django.core.management import call_command
    from scripts.verificar_oracle_dml import main as verificar_oracle

    verificar_oracle()
    call_command("check", "--deploy")
    print("OK DJANGO: validación de despliegue ejecutada; no hay DDL pendiente.")


def iniciar() -> None:
    verificar()
    from django.conf import settings
    from django.core.management import call_command
    from waitress import serve

    # WhiteNoise construye su inventario al crear la aplicación WSGI. En una
    # instalación nueva debemos recolectar primero; si se importa WSGI antes,
    # el proceso conserva un inventario vacío y el portal aparece sin CSS.
    call_command("collectstatic", interactive=False, verbosity=1, clear=True)
    requeridos = (
        "css/portal-v8.css",
        "css/portal.css",
        "images/login-background-claro.png",
    )
    faltantes = [
        nombre for nombre in requeridos
        if not (Path(settings.STATIC_ROOT) / Path(nombre)).is_file()
    ]
    if faltantes:
        raise RuntimeError(
            "collectstatic no generó archivos indispensables: "
            + ", ".join(faltantes)
        )

    # Debe importarse después de collectstatic para que WhiteNoise encuentre
    # los archivos recién creados.
    from config.wsgi import application

    print("OK ESTÁTICOS: CSS, imagen de acceso y WhiteNoise preparados.")
    host = os.environ.get("PORTAL_BIND_HOST", "0.0.0.0").strip()
    puerto = int(os.environ.get("PORTAL_PORT", "8000"))
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
    sub.add_parser("createsuperuser", help="Comprueba el esquema y crea un superusuario")
    return analizador


def main() -> int:
    argumentos = parser().parse_args()
    if argumentos.comando == "check":
        verificar()
    elif argumentos.comando == "start":
        iniciar()
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
