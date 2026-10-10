#!/usr/bin/env python3
"""Falla si Git incluye rutas o asignaciones típicas de secretos."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
RUTAS_PROHIBIDAS = {".env", ".env.local"}
EXTENSIONES_PROHIBIDAS = {".pem", ".key", ".p12", ".pfx"}
ASIGNACION_SECRETA = re.compile(
    rb"(?mi)^(?:SECRET_KEY|DB_PASSWORD|MICROSOFT_CLIENT_SECRET)\s*=\s*\S+"
)
CLAVE_PRIVADA = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")


def archivos_versionados() -> list[Path]:
    salida = subprocess.check_output(
        ["git", "ls-files", "-z"], cwd=BASE
    )
    return [BASE / nombre.decode("utf-8") for nombre in salida.split(b"\0") if nombre]


def main() -> int:
    errores: list[str] = []
    for archivo in archivos_versionados():
        relativo = archivo.relative_to(BASE).as_posix()
        if relativo in RUTAS_PROHIBIDAS or relativo.startswith("secrets/"):
            errores.append(f"ruta secreta versionada: {relativo}")
            continue
        if archivo.suffix.lower() in EXTENSIONES_PROHIBIDAS:
            errores.append(f"archivo de credencial versionado: {relativo}")
            continue
        try:
            contenido = archivo.read_bytes()
        except OSError:
            continue
        if CLAVE_PRIVADA.search(contenido):
            errores.append(f"clave privada detectada: {relativo}")
        if archivo.name.startswith(".env") and ASIGNACION_SECRETA.search(contenido):
            errores.append(f"secreto directo en archivo de entorno: {relativo}")
    if errores:
        raise SystemExit("ERROR SECRETOS GIT:\n- " + "\n- ".join(errores))
    print("OK SECRETOS GIT: no hay archivos secretos ni credenciales directas versionadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
