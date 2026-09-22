#!/usr/bin/env python3
"""PostgreSQL de desarrollo aislado. No modifica el servidor instalado."""
import argparse
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile

BASE = Path(__file__).resolve().parent.parent
RUNTIME = BASE / ".runtime"
DATA = RUNTIME / "postgres"
PORT = int(os.environ.get("LOCAL_PG_PORT", "55432"))
SOCKET = Path(tempfile.gettempdir()) / ("portal-nc-" + hashlib.sha256(str(BASE).encode()).hexdigest()[:12])


def binario(nombre):
    carpeta = os.environ.get("PG_BIN", "")
    encontrado = shutil.which(nombre)
    opciones = [Path(carpeta) / nombre] if carpeta else []
    if encontrado:
        opciones.append(Path(encontrado))
    opciones.extend([Path("/Library/PostgreSQL/18/bin") / nombre, Path("/opt/homebrew/opt/postgresql@18/bin") / nombre])
    for archivo in opciones:
        if archivo.is_file():
            return str(archivo)
    raise SystemExit("No se encontró PostgreSQL. Define PG_BIN apuntando a su carpeta bin.")


def ejecutar(nombre, *argumentos, **kwargs):
    return subprocess.run([binario(nombre), *map(str, argumentos)], check=True, **kwargs)


def iniciar():
    import environ
    import psycopg
    from psycopg import sql

    RUNTIME.mkdir(mode=0o700, exist_ok=True)
    SOCKET.mkdir(mode=0o700, exist_ok=True)
    os.chmod(RUNTIME, 0o700)
    os.chmod(SOCKET, 0o700)
    entorno = BASE / ".env"
    if not entorno.exists():
        secreto = secrets.token_urlsafe(60)
        password = secrets.token_urlsafe(32)
        fd = os.open(entorno, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as archivo:
            archivo.write(f"DEBUG=True\nSECRET_KEY={secreto}\nALLOWED_HOSTS=127.0.0.1,localhost\nDB_NAME=gestion_no_conformidades\nDB_USER=portal_nc\nDB_PASSWORD={password}\nDB_HOST=127.0.0.1\nDB_PORT={PORT}\nSAC_SEQUENCE_SCOPE=TYPE\nREQUIRE_CLOSED_PBI=False\nENABLE_DEMO_DATA=True\n")
    env = environ.Env()
    environ.Env.read_env(entorno)
    if env("DB_HOST") != "127.0.0.1" or env.int("DB_PORT") != PORT:
        raise SystemExit(".env apunta a otra instancia. No se modificó: usa migrate con esa configuración o revisa LOCAL_PG_PORT.")
    if not (DATA / "PG_VERSION").exists():
        ejecutar("initdb", "-D", DATA, "-U", "nc_local_owner", "--auth-local=trust", "--auth-host=scram-sha-256", "--encoding=UTF8", "--locale=C")
    activo = subprocess.run([binario("pg_ctl"), "-D", str(DATA), "status"], capture_output=True).returncode == 0
    if not activo:
        ejecutar("pg_ctl", "-D", DATA, "-l", RUNTIME / "postgres.log", "-o", f"-h 127.0.0.1 -p {PORT} -k '{SOCKET}'", "-w", "start")
    with psycopg.connect(host=str(SOCKET), port=PORT, user="nc_local_owner", dbname="postgres", autocommit=True) as conexion:
        usuario, nombre, password = env("DB_USER"), env("DB_NAME"), env("DB_PASSWORD")
        if not conexion.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", [usuario]).fetchone():
            conexion.execute(sql.SQL("CREATE ROLE {} LOGIN CREATEDB PASSWORD {}").format(sql.Identifier(usuario), sql.Literal(password)))
        if not conexion.execute("SELECT 1 FROM pg_database WHERE datname=%s", [nombre]).fetchone():
            conexion.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(nombre), sql.Identifier(usuario)))
    print(f"PostgreSQL local disponible en 127.0.0.1:{PORT}. Credenciales privadas en .env; no se muestran.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accion", choices=["start", "stop", "status"])
    args = parser.parse_args()
    if args.accion == "start":
        iniciar()
    elif args.accion == "stop":
        ejecutar("pg_ctl", "-D", DATA, "-m", "fast", "-w", "stop")
    else:
        ejecutar("pg_ctl", "-D", DATA, "status")
