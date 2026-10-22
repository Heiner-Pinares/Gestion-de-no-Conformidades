"""Fija de forma explícita la identidad SSH del servidor de correo."""

from __future__ import annotations

import base64
import hashlib
import os
import socket
from pathlib import Path
from tempfile import NamedTemporaryFile

import paramiko
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def _nombre_host(host: str, port: int) -> str:
    return host if port == 22 else f"[{host}]:{port}"


def _huella_sha256(clave: paramiko.PKey) -> str:
    digest = hashlib.sha256(clave.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


class Command(BaseCommand):
    help = (
        "Obtiene y fija la clave pública SSH del servidor de correo. "
        "Nunca autentica ni envía mensajes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--archivo",
            help="Ruta de known_hosts. Por defecto usa CORREO_SSH_KNOWN_HOSTS.",
        )
        parser.add_argument(
            "--si-habilitado",
            action="store_true",
            help="No hace nada cuando CORREO_COMPROMISOS_ENABLED=False.",
        )

    def handle(self, *args, **options):
        if options["si_habilitado"] and not settings.CORREO_COMPROMISOS_ENABLED:
            self.stdout.write("Correo deshabilitado; no se preparó identidad SSH.")
            return

        host = str(settings.CORREO_SSH_HOST).strip()
        port = int(settings.CORREO_SSH_PORT)
        if not host:
            raise CommandError("Falta CORREO_SSH_HOST en .env.")

        destino = Path(options.get("archivo") or settings.CORREO_SSH_KNOWN_HOSTS)
        if not destino.is_absolute():
            destino = Path(settings.BASE_DIR) / destino
        destino = destino.resolve()

        transporte = None
        conexion = None
        try:
            conexion = socket.create_connection(
                (host, port), timeout=settings.CORREO_SSH_TIMEOUT
            )
            transporte = paramiko.Transport(conexion)
            transporte.start_client(timeout=settings.CORREO_SSH_TIMEOUT)
            clave = transporte.get_remote_server_key()
        except (OSError, paramiko.SSHException) as error:
            raise CommandError(
                "No se pudo obtener la identidad SSH del servidor de correo. "
                "Verifica la red corporativa, el host y el puerto."
            ) from error
        finally:
            if transporte is not None:
                transporte.close()
            elif conexion is not None:
                conexion.close()

        nombre = _nombre_host(host, port)
        existentes = paramiko.HostKeys()
        if destino.is_file() and destino.stat().st_size:
            try:
                existentes.load(str(destino))
            except (OSError, paramiko.SSHException) as error:
                raise CommandError(
                    f"El archivo existente no es un known_hosts válido: {destino}"
                ) from error
            claves_host = existentes.lookup(nombre) or {}
            if claves_host:
                anterior = claves_host.get(clave.get_name())
                if anterior is None or anterior.asbytes() != clave.asbytes():
                    raise CommandError(
                        "La identidad SSH recibida no coincide con la ya registrada. "
                        "No se reemplazó el archivo."
                    )

        destino.parent.mkdir(parents=True, exist_ok=True)
        contenido = f"{nombre} {clave.get_name()} {clave.get_base64()}\n"
        temporal = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="ascii",
                newline="\n",
                dir=destino.parent,
                prefix=destino.name + ".",
                suffix=".tmp",
                delete=False,
            ) as archivo:
                temporal = Path(archivo.name)
                archivo.write(contenido)
            os.replace(temporal, destino)
            try:
                destino.chmod(0o600)
            except OSError:
                pass
        except OSError as error:
            if temporal is not None:
                temporal.unlink(missing_ok=True)
            raise CommandError(
                f"No se pudo guardar la identidad SSH en {destino}."
            ) from error

        self.stdout.write(
            self.style.SUCCESS(
                f"Identidad SSH preparada en {destino} ({_huella_sha256(clave)})."
            )
        )
