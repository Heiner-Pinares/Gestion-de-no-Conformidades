#!/usr/bin/env python3
"""Genera el instalador Oracle autocontenido del Portal NC.

El archivo resultante no usa @ ni @@ y se puede ejecutar directamente desde
la ventana de comandos de PL/SQL Developer conectado como USRFACT.
"""

from pathlib import Path


BASE = Path(__file__).resolve().parents[1] / "docs" / "oracle_usrfact"
DESTINO = BASE / "INSTALAR_USRFACT_TODO_EN_UNO.sql"

FUENTES = (
    "00_prevalidacion.sql",
    "01_crear_tablas.sql",
    "02_relaciones_indices.sql",
    "03_triggers_integridad.sql",
    "04_datos_base.sql",
    "05_baseline_django.sql",
    "06_ajustar_identidades.sql",
    "07_permisos.sql",
    "08_prueba_humo.sql",
    "09_validacion_final.sql",
)

CABECERA = """-- ============================================================================
-- PORTAL CLARO - GESTION DE NO CONFORMIDADES
-- INSTALADOR ORACLE 19c TODO EN UNO
-- Esquema propietario: USRFACT
-- Usuarios con acceso: C27826, C28111 y C28134
--
-- Ejecutar el archivo completo conectado como USRFACT en una ventana de
-- comandos de PL/SQL Developer. No requiere archivos SQL adicionales.
-- ============================================================================

SET DEFINE OFF
SET SERVEROUTPUT ON SIZE UNLIMITED
SET ECHO ON
SET FEEDBACK ON
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

ALTER SESSION SET TIME_ZONE = 'UTC';

PROMPT ============================================================
PROMPT Portal NC - instalacion completa y autocontenida en USRFACT
PROMPT ============================================================

"""

PIE = """
PROMPT ============================================================
PROMPT INSTALACION COMPLETADA Y VALIDADA
PROMPT ============================================================

EXIT SUCCESS
"""


def main() -> None:
    partes = [CABECERA]
    for nombre in FUENTES:
        ruta = BASE / nombre
        contenido = ruta.read_text(encoding="utf-8").rstrip()
        partes.append(
            f"-- ============================================================================\n"
            f"-- INICIO DEL MODULO INTEGRADO: {nombre}\n"
            f"-- ============================================================================\n"
            f"{contenido}\n"
            f"-- FIN DEL MODULO INTEGRADO: {nombre}\n"
        )
    partes.append(PIE)
    with DESTINO.open("w", encoding="utf-8", newline="\n") as archivo:
        archivo.write("\n".join(partes))
    print(DESTINO)


if __name__ == "__main__":
    main()
