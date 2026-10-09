#!/usr/bin/env python3
"""Verificación de solo lectura previa al arranque del portal en Oracle."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def main() -> int:
    exigir(connection.vendor == "oracle", "La conexión activa no usa Oracle.")
    esquema = settings.DB_SCHEMA.upper()
    usuario_configurado = settings.DATABASES["default"]["USER"].upper()
    exigir(usuario_configurado != esquema, "La aplicación no debe conectarse como propietaria USRFACT.")

    manifest = json.loads(
        (BASE / "docs" / "oracle_usrfact" / "manifest_esquema.json").read_text(encoding="utf-8")
    )
    esperadas = {nombre.upper(): {c.upper() for c in datos["columns"]}
                 for nombre, datos in manifest["tables"].items()}

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT SYS_CONTEXT('USERENV','SESSION_USER'), "
            "SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM dual"
        )
        usuario_sesion, esquema_actual = cursor.fetchone()
        exigir(usuario_sesion.upper() == usuario_configurado, "SESSION_USER no coincide con DB_USER.")
        exigir(esquema_actual.upper() == esquema, "CURRENT_SCHEMA no apunta a USRFACT.")

        cursor.execute("SELECT privilege FROM session_privs")
        privilegios_sistema = {fila[0] for fila in cursor.fetchall()}
        peligrosos = privilegios_sistema - {"CREATE SESSION"}
        exigir(not peligrosos,
               "La cuenta tiene privilegios de sistema fuera de CREATE SESSION: "
               + ", ".join(sorted(peligrosos)))

        cursor.execute(
            "SELECT table_name, column_name FROM all_tab_columns "
            "WHERE owner = %s ORDER BY table_name, column_id",
            [esquema],
        )
        reales: dict[str, set[str]] = {}
        for tabla, columna in cursor.fetchall():
            if tabla in esperadas:
                reales.setdefault(tabla, set()).add(columna)
        exigir(set(reales) == set(esperadas),
               f"Inventario distinto. Faltan tablas: {sorted(set(esperadas) - set(reales))}")
        for tabla, columnas in esperadas.items():
            exigir(reales[tabla] == columnas,
                   f"Columnas distintas en {tabla}: faltan={sorted(columnas-reales[tabla])}, "
                   f"sobran={sorted(reales[tabla]-columnas)}")

        cursor.execute(
            "SELECT table_name, privilege FROM all_tab_privs "
            "WHERE owner = %s AND grantee = %s "
            "AND privilege IN ('SELECT','INSERT','UPDATE','DELETE')",
            [esquema, usuario_sesion.upper()],
        )
        permisos = {(tabla, privilegio) for tabla, privilegio in cursor.fetchall()
                    if tabla in esperadas}
        requeridos = {(tabla, privilegio) for tabla in esperadas
                      for privilegio in ("SELECT", "INSERT", "UPDATE", "DELETE")}
        exigir(permisos == requeridos,
               f"Permisos DML incompletos: {sorted(requeridos - permisos)}")
        cursor.execute(
            "SELECT table_name, privilege FROM all_tab_privs "
            "WHERE owner = %s AND grantee = %s",
            [esquema, usuario_sesion.upper()],
        )
        privilegios_objeto = {(tabla, privilegio) for tabla, privilegio in cursor.fetchall()
                              if tabla in esperadas}
        extras = privilegios_objeto - requeridos
        exigir(not extras, f"La cuenta tiene permisos de objeto adicionales: {sorted(extras)}")

        for tabla in sorted(esperadas):
            cursor.execute(f'SELECT 1 FROM "{esquema}"."{tabla}" WHERE 1=0')

        cursor.execute("SELECT COUNT(*) FROM tbl_django_migrations_nc")
        exigir(cursor.fetchone()[0] == 56, "La línea base Django no contiene 56 migraciones.")
        cursor.execute(
            "SELECT data_type FROM all_tab_columns WHERE owner=%s "
            "AND table_name='TBL_ARCHIVO_EVIDENCIA_NC' AND column_name='CONTENIDO'",
            [esquema],
        )
        fila = cursor.fetchone()
        exigir(fila and fila[0] == "BLOB", "El contenido de evidencias no está almacenado como BLOB.")

    print(
        f"OK ORACLE DML: usuario={usuario_sesion}, esquema={esquema_actual}, "
        f"24 tablas, 229 columnas, 96 permisos DML y evidencias BLOB."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR ORACLE DML: {error}", file=sys.stderr)
        raise SystemExit(1)
