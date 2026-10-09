#!/usr/bin/env python3
"""Administración del Portal Claro."""
import os
import sys
from pathlib import Path

import environ

if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent
    local_env = base_dir / ".env.local"
    if local_env.exists():
        environ.Env.read_env(local_env)
    environ.Env.read_env(base_dir / ".env")
    motor = os.environ.get("DB_ENGINE", "").strip().lower()
    comandos_esquema = {
        "migrate", "makemigrations", "sqlmigrate", "squashmigrations", "test", "flush",
    }
    if motor == "oracle" and len(sys.argv) > 1 and sys.argv[1] in comandos_esquema:
        raise SystemExit(
            f"El comando '{sys.argv[1]}' está bloqueado en Oracle. "
            "Los cambios de esquema solo los ejecuta el DBA mediante SQL revisado."
        )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
