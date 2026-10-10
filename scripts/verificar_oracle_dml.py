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
import oracledb  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402
from django.db.migrations.loader import MigrationLoader  # noqa: E402

TRIGGERS_REQUERIDOS = {
    "TRG_USUARIO_JSON_NC",
    "TRG_USUARIO_ROLES_SYNC_NC",
    "TRG_PROCESO_JSON_NC",
    "TRG_PROCESO_VALID_SYNC_NC",
    "TRG_AUDITORIA_JSON_NC",
    "TRG_CICLO_JSON_NC",
    "TRG_HISTORIAL_JSON_NC",
    "TRG_MATRIZ_CATALOGOS_NC",
    "TRG_REGISTRO_CATALOGOS_NC",
    "TRG_REGISTRO_UPDATED_NC",
    "TRG_ACTIVIDAD_UPDATED_NC",
}


def exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise RuntimeError(mensaje)


def migraciones_del_codigo() -> set[tuple[str, str]]:
    """Devuelve la línea base que corresponde exactamente a este checkout."""
    return set(MigrationLoader(None, ignore_no_migrations=True).disk_migrations)


def main() -> int:
    exigir(connection.vendor == "oracle", "La conexión activa no usa Oracle.")
    esquema = settings.DB_SCHEMA.upper()
    usuario_configurado = str(settings.DATABASES["default"]["USER"])
    exigir(
        usuario_configurado.upper() != esquema,
        "La aplicación no debe conectarse como propietaria USRFACT.",
    )

    manifest = json.loads(
        (BASE / "docs" / "oracle_usrfact" / "manifest_esquema.json").read_text(
            encoding="utf-8"
        )
    )
    esperadas = {
        nombre.upper(): {columna.upper() for columna in datos["columns"]}
        for nombre, datos in manifest["tables"].items()
    }

    connection.ensure_connection()
    version_oracle = str(getattr(connection.connection, "version", "desconocida"))
    try:
        version_mayor = int(version_oracle.split(".", 1)[0])
    except ValueError:
        version_mayor = 0
    exigir(
        version_mayor >= 19,
        f"Oracle 19c o superior es requerido; se detectó {version_oracle}.",
    )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT SYS_CONTEXT('USERENV','SESSION_USER'), "
            "SYS_CONTEXT('USERENV','CURRENT_SCHEMA'), "
            "SYS_CONTEXT('USERENV','SERVICE_NAME') FROM dual"
        )
        usuario_sesion, esquema_actual, servicio = cursor.fetchone()
        exigir(
            usuario_sesion.upper() == usuario_configurado.upper(),
            "SESSION_USER no coincide con DB_USER.",
        )
        exigir(esquema_actual.upper() == esquema, "CURRENT_SCHEMA no apunta a USRFACT.")

        cursor.execute("SELECT privilege FROM session_privs")
        privilegios_sistema = {fila[0] for fila in cursor.fetchall()}
        peligrosos = privilegios_sistema - {"CREATE SESSION"}
        exigir(
            not peligrosos,
            "La cuenta tiene privilegios de sistema fuera de CREATE SESSION: "
            + ", ".join(sorted(peligrosos)),
        )

        cursor.execute(
            "SELECT table_name, column_name FROM all_tab_columns "
            "WHERE owner = %s ORDER BY table_name, column_id",
            [esquema],
        )
        reales: dict[str, set[str]] = {}
        for tabla, columna in cursor.fetchall():
            if tabla in esperadas:
                reales.setdefault(tabla, set()).add(columna)
        exigir(
            set(reales) == set(esperadas),
            f"Inventario distinto. Faltan tablas: {sorted(set(esperadas) - set(reales))}",
        )
        for tabla, columnas in esperadas.items():
            exigir(
                reales[tabla] == columnas,
                f"Columnas distintas en {tabla}: faltan={sorted(columnas-reales[tabla])}, "
                f"sobran={sorted(reales[tabla]-columnas)}",
            )

        cursor.execute(
            "SELECT table_name, privilege FROM all_tab_privs "
            "WHERE table_schema = %s AND grantee = %s "
            "AND privilege IN ('SELECT','INSERT','UPDATE','DELETE')",
            [esquema, usuario_sesion.upper()],
        )
        permisos = {
            (tabla, privilegio)
            for tabla, privilegio in cursor.fetchall()
            if tabla in esperadas
        }
        requeridos = {
            (tabla, privilegio)
            for tabla in esperadas
            for privilegio in ("SELECT", "INSERT", "UPDATE", "DELETE")
        }
        exigir(permisos == requeridos, f"Permisos DML incompletos: {sorted(requeridos-permisos)}")
        cursor.execute(
            "SELECT table_name, privilege FROM all_tab_privs "
            "WHERE table_schema = %s AND grantee = %s",
            [esquema, usuario_sesion.upper()],
        )
        privilegios_objeto = {
            (tabla, privilegio)
            for tabla, privilegio in cursor.fetchall()
            if tabla in esperadas
        }
        extras = privilegios_objeto - requeridos
        exigir(not extras, f"La cuenta tiene permisos de objeto adicionales: {sorted(extras)}")

        for tabla in sorted(esperadas):
            cursor.execute(f'SELECT 1 FROM "{esquema}"."{tabla}" WHERE 1=0')

        cursor.execute(
            "SELECT object_name, status FROM all_objects "
            "WHERE owner=%s AND object_type='TRIGGER'",
            [esquema],
        )
        estados_trigger = {nombre: estado for nombre, estado in cursor.fetchall()}
        faltantes_trigger = TRIGGERS_REQUERIDOS - set(estados_trigger)
        invalidos_trigger = {
            nombre
            for nombre in TRIGGERS_REQUERIDOS
            if estados_trigger.get(nombre) != "VALID"
        }
        exigir(not faltantes_trigger, f"Faltan triggers requeridos: {sorted(faltantes_trigger)}")
        exigir(not invalidos_trigger, f"Hay triggers inválidos: {sorted(invalidos_trigger)}")
        cursor.execute(
            "SELECT trigger_name, status FROM all_triggers WHERE owner=%s",
            [esquema],
        )
        triggers_deshabilitados = {
            nombre
            for nombre, estado in cursor.fetchall()
            if nombre in TRIGGERS_REQUERIDOS and estado != "ENABLED"
        }
        exigir(
            not triggers_deshabilitados,
            f"Hay triggers deshabilitados: {sorted(triggers_deshabilitados)}",
        )

        cursor.execute("SELECT app, name FROM tbl_django_migrations_nc")
        migraciones_bd = {(app, name) for app, name in cursor.fetchall()}
        migraciones_codigo = migraciones_del_codigo()
        exigir(
            migraciones_bd == migraciones_codigo,
            "La línea base Django no coincide con el código: "
            f"faltan={sorted(migraciones_codigo-migraciones_bd)}, "
            f"sobran={sorted(migraciones_bd-migraciones_codigo)}",
        )

        comprobaciones_catalogo = (
            ("tbl_catalogo_nc", 29, "Faltan valores indispensables en tbl_catalogo_nc."),
            ("tbl_configuracion_impacto_nc", 1, "Falta la configuración de impacto."),
            ("tbl_configuracion_urgencia_nc", 2, "Faltan configuraciones de urgencia."),
            ("tbl_matriz_prioridad_nc", 9, "La matriz de prioridad está incompleta."),
            ("tbl_pregunta_causa_nc", 32, "Faltan preguntas de causa raíz."),
        )
        for tabla, minimo, mensaje in comprobaciones_catalogo:
            cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
            exigir(cursor.fetchone()[0] >= minimo, mensaje)

        cursor.execute(
            "SELECT data_type FROM all_tab_columns WHERE owner=%s "
            "AND table_name='TBL_ARCHIVO_EVIDENCIA_NC' AND column_name='CONTENIDO'",
            [esquema],
        )
        fila = cursor.fetchone()
        exigir(
            fila and fila[0] == "BLOB",
            "El contenido de evidencias no está almacenado como BLOB.",
        )

    print(f"Servicio Oracle: {servicio}")
    print(f"Versión Oracle: {version_oracle}")
    print(f"Modo python-oracledb: {'Thin' if oracledb.is_thin_mode() else 'Thick'}")
    print(f"Usuario de sesión: {usuario_sesion}")
    print(f"Esquema activo: {esquema_actual}")
    print(
        "OK ORACLE DML: 24 tablas, 229 columnas, 96 permisos DML, "
        f"{len(migraciones_bd)} migraciones, {len(TRIGGERS_REQUERIDOS)} triggers y evidencias BLOB."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR ORACLE DML: {error}", file=sys.stderr)
        raise SystemExit(1)
