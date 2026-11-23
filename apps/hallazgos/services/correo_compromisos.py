"""Notificaciones del portal por sendmail remoto a través de SSH."""

from __future__ import annotations

import logging
import shlex
import socket
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formataddr, formatdate, getaddresses, make_msgid
from pathlib import Path
from urllib.parse import urljoin

import paramiko
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.catalogos.services import TIPO_COPIA, TIPO_PARA, destinatarios_adicionales
from apps.hallazgos.models import Accion, Hallazgo, HistorialHallazgo


logger = logging.getLogger(__name__)


class CorreoCompromisoError(Exception):
    """Error controlado, apto para mostrarse sin revelar credenciales."""

    def __init__(self, mensaje: str, *, codigo: str, incierto: bool = False):
        super().__init__(mensaje)
        self.codigo = codigo
        self.incierto = incierto


@dataclass(frozen=True)
class ResultadoCorreo:
    aceptado: bool
    duplicado: bool = False
    codigo_salida: int | None = None


def _normalizar_direcciones(valores: list[str]) -> list[str]:
    """Analiza, valida y elimina duplicados conservando el orden."""

    resultado: list[str] = []
    vistos: set[str] = set()
    for _, direccion in getaddresses(valores):
        direccion = direccion.strip()
        try:
            validate_email(direccion)
        except ValidationError as error:
            raise CorreoCompromisoError(
                "El perfil del destinatario contiene una dirección de correo no válida.",
                codigo="DIRECCION_INVALIDA",
            ) from error
        clave = direccion.casefold()
        if clave not in vistos:
            vistos.add(clave)
            resultado.append(direccion)
    return resultado


class CorreoCompromisoService:
    EVENTOS_NO_REPETIBLES = {
        "CORREO_COMPROMISO_INICIADO",
        "CORREO_COMPROMISO_ACEPTADO",
        "CORREO_COMPROMISO_INCIERTO",
    }
    EVENTOS_REPROGRAMACION_NO_REPETIBLES = {
        "CORREO_REPROGRAMACION_INICIADO",
        "CORREO_REPROGRAMACION_ACEPTADO",
        "CORREO_REPROGRAMACION_INCIERTO",
    }
    EVENTOS_HALLAZGO_NO_REPETIBLES = {
        "CORREO_HALLAZGO_INICIADO",
        "CORREO_HALLAZGO_ACEPTADO",
        "CORREO_HALLAZGO_INCIERTO",
    }

    @staticmethod
    def _configuracion() -> None:
        if not settings.CORREO_COMPROMISOS_ENABLED:
            raise CorreoCompromisoError(
                "El envío de correos del portal está deshabilitado en la configuración del servidor.",
                codigo="DESHABILITADO",
            )
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
            raise CorreoCompromisoError(
                "Falta configurar el envío corporativo: " + ", ".join(faltantes) + ".",
                codigo="CONFIGURACION_INCOMPLETA",
            )

    @classmethod
    def _destinatarios_responsable(cls, responsable) -> tuple[list[str], list[str]]:
        """Aplica la misma regla de destinatarios a hallazgos y compromisos."""

        if responsable is None or not responsable.is_active:
            raise CorreoCompromisoError(
                "El registro no tiene un responsable activo.", codigo="SIN_RESPONSABLE"
            )
        if not responsable.email.strip():
            raise CorreoCompromisoError(
                "El responsable seleccionado no tiene un correo registrado.",
                codigo="SIN_CORREO_RESPONSABLE",
            )

        adicionales = destinatarios_adicionales()
        para = _normalizar_direcciones([
            responsable.email,
            *adicionales[TIPO_PARA],
        ])
        copia: list[str] = []
        jefe = responsable.jefe
        if jefe and jefe.is_active:
            if not jefe.email.strip():
                raise CorreoCompromisoError(
                    "El jefe del responsable no tiene un correo registrado.",
                    codigo="SIN_CORREO_JEFE",
                )
            copia.append(jefe.email)
        copia = _normalizar_direcciones([
            *copia,
            *adicionales[TIPO_COPIA],
        ])
        claves_para = {direccion.casefold() for direccion in para}
        copia = [
            direccion for direccion in copia
            if direccion.casefold() not in claves_para
        ]
        return para, copia

    @classmethod
    def construir_mensaje(cls, accion: Accion) -> tuple[EmailMessage, list[str]]:
        cls._configuracion()
        accion = Accion.objects.select_related(
            "responsable__jefe", "ciclo__hallazgo"
        ).get(pk=accion.pk)
        responsable = accion.responsable
        para, copia = cls._destinatarios_responsable(responsable)

        if not settings.CORREO_REMITENTE_EMAIL.strip():
            raise CorreoCompromisoError(
                "El remitente del portal no está configurado.", codigo="SIN_REMITENTE"
            )
        remitente = _normalizar_direcciones([settings.CORREO_REMITENTE_EMAIL])

        hallazgo = accion.ciclo.hallazgo
        url = urljoin(
            settings.PORTAL_PUBLIC_URL.rstrip("/") + "/",
            reverse("hallazgo_acciones_seguimiento", args=[hallazgo.pk]).lstrip("/"),
        )
        contexto = {
            "responsable_nombre": responsable.get_full_name() or responsable.username,
            "codigo_hallazgo": hallazgo.codigo,
            "codigo_actividad": accion.codigo,
            "accion": accion.descripcion,
            "tipo_accion": accion.get_tipo_display(),
            "fet_compromiso": accion.fecha_vigente.strftime("%d/%m/%Y"),
            "estado": accion.get_estado_display(),
            "url_compromiso": url,
        }
        html = render_to_string("correos/compromiso_asignado.html", contexto)
        texto = (
            f"Hola {contexto['responsable_nombre']},\n\n"
            f"Se te asignó el compromiso {accion.codigo} del hallazgo {hallazgo.codigo}.\n"
            f"Acción: {accion.descripcion}\n"
            f"Tipo: {accion.get_tipo_display()}\n"
            f"FET compromiso: {contexto['fet_compromiso']}\n"
            f"Estado: {accion.get_estado_display()}\n\n"
            f"Consulta el compromiso en {url}\n"
        )
        dominio = remitente[0].rsplit("@", 1)[-1]
        mensaje = EmailMessage(policy=SMTP)
        mensaje["From"] = formataddr(
            (settings.CORREO_REMITENTE_NOMBRE, remitente[0])
        )
        mensaje["To"] = ", ".join(para)
        if copia:
            mensaje["Cc"] = ", ".join(copia)
        mensaje["Subject"] = f"Nuevo compromiso asignado: {accion.codigo}"
        mensaje["Date"] = formatdate(localtime=True)
        mensaje["Message-ID"] = make_msgid(domain=dominio)
        mensaje.set_content(texto)
        mensaje.add_alternative(html, subtype="html")
        return mensaje, [*para, *copia]

    @classmethod
    def construir_mensaje_hallazgo(
        cls, hallazgo: Hallazgo
    ) -> tuple[EmailMessage, list[str]]:
        """Construye el aviso de registro para el responsable del hallazgo."""

        cls._configuracion()
        hallazgo = Hallazgo.objects.select_related(
            "responsable__jefe",
            "registrado_por",
            "proceso",
            "subproceso",
            "tipo_registro",
        ).get(pk=hallazgo.pk)
        responsable = hallazgo.responsable
        registrador = hallazgo.registrado_por
        para, copia = cls._destinatarios_responsable(responsable)
        remitente = _normalizar_direcciones([settings.CORREO_REMITENTE_EMAIL])
        url = urljoin(
            settings.PORTAL_PUBLIC_URL.rstrip("/") + "/",
            reverse("hallazgo_detalle", args=[hallazgo.pk]).lstrip("/"),
        )
        fecha_deteccion = hallazgo.fecha_deteccion
        if fecha_deteccion and timezone.is_aware(fecha_deteccion):
            fecha_deteccion = timezone.localtime(fecha_deteccion)
        contexto = {
            "codigo_hallazgo": hallazgo.codigo,
            "proceso": str(hallazgo.proceso),
            "subproceso": str(hallazgo.subproceso) if hallazgo.subproceso else "No especificado",
            "tipo_registro": str(hallazgo.tipo_registro),
            "fecha_deteccion": (
                fecha_deteccion.strftime("%d/%m/%Y")
                if fecha_deteccion else "No especificada"
            ),
            "nombre_registrador": registrador.get_full_name() or registrador.username,
            "nombre_responsable": responsable.get_full_name() or responsable.username,
            "mismo_responsable": registrador.pk == responsable.pk,
            "es_critico": hallazgo.es_critica == "SI",
            "descripcion": hallazgo.descripcion,
            "url_hallazgo": url,
        }
        html = render_to_string("correos/nuevo_hallazgo.html", contexto)
        texto = (
            f"Hola {contexto['nombre_responsable']},\n\n"
            f"Se registró el hallazgo {hallazgo.codigo}.\n"
            f"Proceso: {contexto['proceso']}\n"
            f"Subproceso: {contexto['subproceso']}\n"
            f"Tipo de registro: {contexto['tipo_registro']}\n"
            f"Fecha de detección: {contexto['fecha_deteccion']}\n"
            f"Registrado por: {contexto['nombre_registrador']}\n"
            f"Responsable: {contexto['nombre_responsable']}\n"
            f"Descripción: {hallazgo.descripcion}\n\n"
            f"Revisa el hallazgo en {url}\n"
        )
        dominio = remitente[0].rsplit("@", 1)[-1]
        mensaje = EmailMessage(policy=SMTP)
        mensaje["From"] = formataddr(
            (settings.CORREO_REMITENTE_NOMBRE, remitente[0])
        )
        mensaje["To"] = ", ".join(para)
        if copia:
            mensaje["Cc"] = ", ".join(copia)
        mensaje["Subject"] = f"Nuevo hallazgo registrado: {hallazgo.codigo}"
        mensaje["Date"] = formatdate(localtime=True)
        mensaje["Message-ID"] = make_msgid(domain=dominio)
        mensaje.set_content(texto)
        mensaje.add_alternative(html, subtype="html")
        return mensaje, [*para, *copia]

    @classmethod
    def construir_mensaje_reprogramacion(
        cls, solicitud: HistorialHallazgo
    ) -> tuple[EmailMessage, list[str]]:
        """Construye el aviso dirigido al aprobador elegido en la solicitud."""

        cls._configuracion()
        solicitud = HistorialHallazgo.objects.select_related(
            "usuario",
            "accion_relacionada__responsable",
            "accion_relacionada__ciclo__hallazgo",
        ).get(pk=solicitud.pk, accion="SOLICITUD_REPROGRAMACION")
        accion = solicitud.accion_relacionada
        if accion is None:
            raise CorreoCompromisoError(
                "La solicitud no está vinculada a una actividad.",
                codigo="SIN_ACTIVIDAD",
            )

        metadata = dict(solicitud.metadata_json or {})
        aprobador_id = metadata.get("aprobador_id")
        aprobador = get_user_model().objects.filter(
            pk=aprobador_id, is_active=True
        ).first()
        if aprobador is None:
            raise CorreoCompromisoError(
                "El responsable de jefatura seleccionado ya no está activo.",
                codigo="SIN_APROBADOR",
            )
        if not aprobador.email.strip():
            raise CorreoCompromisoError(
                "El responsable de jefatura seleccionado no tiene un correo registrado.",
                codigo="SIN_CORREO_APROBADOR",
            )

        para = _normalizar_direcciones([aprobador.email])
        solicitante = solicitud.usuario
        if not solicitante.email.strip():
            raise CorreoCompromisoError(
                "El usuario que solicitó la reprogramación no tiene un correo registrado.",
                codigo="SIN_CORREO_SOLICITANTE",
            )
        copia = _normalizar_direcciones([solicitante.email])
        claves_para = {direccion.casefold() for direccion in para}
        copia = [
            direccion
            for direccion in copia
            if direccion.casefold() not in claves_para
        ]
        remitente = _normalizar_direcciones([settings.CORREO_REMITENTE_EMAIL])
        hallazgo = accion.ciclo.hallazgo
        url = urljoin(
            settings.PORTAL_PUBLIC_URL.rstrip("/") + "/",
            reverse("hallazgo_detalle", args=[hallazgo.pk]).lstrip("/"),
        )

        def fecha_legible(valor: str) -> str:
            try:
                return date.fromisoformat(valor).strftime("%d/%m/%Y")
            except (TypeError, ValueError):
                return valor or "—"

        responsable = accion.responsable
        contexto = {
            "nombre_aprobador": aprobador.get_full_name() or aprobador.username,
            "codigo_no_conformidad": hallazgo.codigo,
            "codigo_accion": accion.codigo,
            "accion": accion.descripcion,
            "responsable": (
                responsable.get_full_name() or responsable.username
                if responsable
                else "Sin responsable"
            ),
            "fecha_vigente": fecha_legible(metadata.get("fecha_anterior", "")),
            "nueva_fecha": fecha_legible(metadata.get("nueva_fecha", "")),
            "motivo_reprogramacion": solicitud.comentario,
            "url_solicitud": url,
        }
        html = render_to_string("correos/reprogramacion_pendiente.html", contexto)
        texto = (
            f"Hola {contexto['nombre_aprobador']},\n\n"
            f"Tienes una solicitud de reprogramación pendiente para "
            f"{accion.codigo}, vinculada a {hallazgo.codigo}.\n"
            f"Acción: {accion.descripcion}\n"
            f"Responsable: {contexto['responsable']}\n"
            f"Fecha vigente: {contexto['fecha_vigente']}\n"
            f"Nueva fecha propuesta: {contexto['nueva_fecha']}\n"
            f"Motivo: {solicitud.comentario}\n\n"
            f"Revisa la solicitud en {url}\n"
        )
        dominio = remitente[0].rsplit("@", 1)[-1]
        mensaje = EmailMessage(policy=SMTP)
        mensaje["From"] = formataddr(
            (settings.CORREO_REMITENTE_NOMBRE, remitente[0])
        )
        mensaje["To"] = ", ".join(para)
        if copia:
            mensaje["Cc"] = ", ".join(copia)
        mensaje["Subject"] = f"Reprogramación pendiente de aprobación: {accion.codigo}"
        mensaje["Date"] = formatdate(localtime=True)
        mensaje["Message-ID"] = make_msgid(domain=dominio)
        mensaje.set_content(texto)
        mensaje.add_alternative(html, subtype="html")
        return mensaje, [*para, *copia]

    @staticmethod
    def _enviar_sendmail(mensaje: EmailMessage, destinatarios: list[str]) -> int:
        if not destinatarios:
            raise CorreoCompromisoError(
                "No existe ningún destinatario válido para el correo.",
                codigo="SIN_DESTINATARIOS",
            )

        cliente = paramiko.SSHClient()
        envio_iniciado = False
        try:
            known_hosts = Path(settings.CORREO_SSH_KNOWN_HOSTS)
            if not known_hosts.is_absolute():
                known_hosts = Path(settings.BASE_DIR) / known_hosts
            try:
                if not known_hosts.is_file() or known_hosts.stat().st_size == 0:
                    raise FileNotFoundError(str(known_hosts))
                cliente.load_host_keys(str(known_hosts))
            except (OSError, paramiko.SSHException) as error:
                raise CorreoCompromisoError(
                    "Falta preparar la identidad SSH del servidor de correo. "
                    "Ejecuta scripts\\preparar_identidad_correo_windows.ps1 "
                    "como administrador.",
                    codigo="SSH_IDENTIDAD_NO_PREPARADA",
                ) from error

            # La identidad se fija durante la configuración. El proceso web solo
            # lee el archivo y nunca necesita permisos de escritura para enviar.
            cliente.set_missing_host_key_policy(paramiko.RejectPolicy())
            cliente.connect(
                hostname=settings.CORREO_SSH_HOST,
                port=settings.CORREO_SSH_PORT,
                username=settings.CORREO_SSH_USER,
                password=settings.CORREO_SSH_PASSWORD,
                timeout=settings.CORREO_SSH_TIMEOUT,
                banner_timeout=settings.CORREO_SSH_TIMEOUT,
                auth_timeout=settings.CORREO_SSH_TIMEOUT,
                allow_agent=False,
                look_for_keys=False,
            )
            comando = "sendmail -i " + " ".join(
                shlex.quote(direccion) for direccion in destinatarios
            )
            entrada, salida, errores = cliente.exec_command(
                comando, timeout=settings.CORREO_SSH_TIMEOUT
            )
            envio_iniciado = True
            entrada.write(mensaje.as_bytes())
            entrada.flush()
            entrada.channel.shutdown_write()
            codigo = salida.channel.recv_exit_status()
            if codigo != 0:
                detalle = errores.read(500).decode("utf-8", errors="replace").strip()
                logger.warning(
                    "sendmail rechazó un compromiso (código=%s, detalle=%s)",
                    codigo,
                    detalle[:300] or "sin detalle",
                )
                raise CorreoCompromisoError(
                    f"El servidor de correo rechazó el mensaje (código {codigo}).",
                    codigo="SENDMAIL_RECHAZADO",
                )
            return codigo
        except paramiko.AuthenticationException as error:
            raise CorreoCompromisoError(
                "El servidor de correo rechazó las credenciales SSH.",
                codigo="SSH_AUTENTICACION",
            ) from error
        except paramiko.BadHostKeyException as error:
            raise CorreoCompromisoError(
                "La identidad SSH del servidor de correo cambió; el envío fue bloqueado.",
                codigo="SSH_IDENTIDAD",
            ) from error
        except CorreoCompromisoError:
            raise
        except (paramiko.ssh_exception.NoValidConnectionsError, socket.timeout, TimeoutError) as error:
            raise CorreoCompromisoError(
                "No se pudo acceder al servidor de correo. Verifica la red corporativa o VPN.",
                codigo="SSH_INACCESIBLE",
                incierto=envio_iniciado,
            ) from error
        except (paramiko.SSHException, OSError) as error:
            mensaje_error = (
                "El resultado del envío es incierto; no se reenviará automáticamente."
                if envio_iniciado
                else "No se pudo establecer la conexión segura con el servidor de correo."
            )
            raise CorreoCompromisoError(
                mensaje_error,
                codigo="ENVIO_INCIERTO" if envio_iniciado else "SSH_CONEXION",
                incierto=envio_iniciado,
            ) from error
        finally:
            cliente.close()

    @classmethod
    def enviar_asignacion(cls, *, accion: Accion, usuario) -> ResultadoCorreo:
        """Envía una sola vez y deja trazabilidad en la tabla de historial."""

        with transaction.atomic():
            accion = Accion.objects.select_for_update().select_related(
                "ciclo__hallazgo"
            ).get(pk=accion.pk)
            hallazgo = accion.ciclo.hallazgo
            if HistorialHallazgo.objects.filter(
                accion_relacionada=accion,
                accion__in=cls.EVENTOS_NO_REPETIBLES,
            ).exists():
                return ResultadoCorreo(aceptado=False, duplicado=True)
            intento = HistorialHallazgo.objects.create(
                hallazgo=hallazgo,
                usuario=usuario,
                accion="CORREO_COMPROMISO_INICIADO",
                accion_relacionada=accion,
                estado_anterior=hallazgo.estado,
                estado_nuevo=hallazgo.estado,
                comentario=f"Inicio del envío de asignación para {accion.codigo}.",
                metadata_json={"accion": accion.codigo},
            )

        try:
            mensaje, destinatarios = cls.construir_mensaje(accion)
            codigo = cls._enviar_sendmail(mensaje, destinatarios)
        except CorreoCompromisoError as error:
            intento.accion = (
                "CORREO_COMPROMISO_INCIERTO"
                if error.incierto
                else "CORREO_COMPROMISO_FALLIDO"
            )
            intento.comentario = str(error)
            intento.metadata_json = {
                "accion": accion.codigo,
                "resultado": error.codigo,
            }
            intento.save(update_fields=["accion", "comentario", "metadata_json"])
            raise

        intento.accion = "CORREO_COMPROMISO_ACEPTADO"
        intento.comentario = (
            "sendmail aceptó el mensaje. Esto no confirma la entrega final en el buzón."
        )
        intento.metadata_json = {
            "accion": accion.codigo,
            "responsable_id": accion.responsable_id,
            "jefe_id": accion.responsable.jefe_id if accion.responsable else None,
            "codigo_salida": codigo,
        }
        intento.save(update_fields=["accion", "comentario", "metadata_json"])
        return ResultadoCorreo(aceptado=True, codigo_salida=codigo)

    @classmethod
    def enviar_nuevo_hallazgo(
        cls, *, hallazgo: Hallazgo, usuario
    ) -> ResultadoCorreo:
        """Notifica una sola vez el registro sin afectar el hallazgo si falla."""

        with transaction.atomic():
            hallazgo = Hallazgo.objects.select_for_update().get(pk=hallazgo.pk)
            if HistorialHallazgo.objects.filter(
                hallazgo=hallazgo,
                accion__in=cls.EVENTOS_HALLAZGO_NO_REPETIBLES,
            ).exists():
                return ResultadoCorreo(aceptado=False, duplicado=True)
            intento = HistorialHallazgo.objects.create(
                hallazgo=hallazgo,
                usuario=usuario,
                accion="CORREO_HALLAZGO_INICIADO",
                estado_anterior=hallazgo.estado,
                estado_nuevo=hallazgo.estado,
                comentario=f"Inicio del aviso de registro para {hallazgo.codigo}.",
                metadata_json={"hallazgo": hallazgo.codigo},
            )

        try:
            mensaje, destinatarios = cls.construir_mensaje_hallazgo(hallazgo)
            codigo = cls._enviar_sendmail(mensaje, destinatarios)
        except CorreoCompromisoError as error:
            intento.accion = (
                "CORREO_HALLAZGO_INCIERTO"
                if error.incierto
                else "CORREO_HALLAZGO_FALLIDO"
            )
            intento.comentario = str(error)
            intento.metadata_json = {
                "hallazgo": hallazgo.codigo,
                "resultado": error.codigo,
            }
            intento.save(update_fields=["accion", "comentario", "metadata_json"])
            raise

        intento.accion = "CORREO_HALLAZGO_ACEPTADO"
        intento.comentario = (
            "sendmail aceptó el aviso del nuevo hallazgo. Esto no confirma la "
            "entrega final en el buzón."
        )
        intento.metadata_json = {
            "hallazgo": hallazgo.codigo,
            "responsable_id": hallazgo.responsable_id,
            "jefe_id": hallazgo.responsable.jefe_id,
            "codigo_salida": codigo,
        }
        intento.save(update_fields=["accion", "comentario", "metadata_json"])
        return ResultadoCorreo(aceptado=True, codigo_salida=codigo)

    @classmethod
    def enviar_reprogramacion(
        cls, *, solicitud: HistorialHallazgo, usuario
    ) -> ResultadoCorreo:
        """Notifica una sola vez al aprobador sin afectar la solicitud guardada."""

        with transaction.atomic():
            # Bloquear solo la fila de historial. Incluir la relación opcional
            # produce un OUTER JOIN que PostgreSQL y Oracle no permiten con
            # FOR UPDATE sobre el lado anulable.
            solicitud = HistorialHallazgo.objects.select_for_update().get(
                pk=solicitud.pk, accion="SOLICITUD_REPROGRAMACION"
            )
            accion = solicitud.accion_relacionada
            if accion is None:
                raise CorreoCompromisoError(
                    "La solicitud no está vinculada a una actividad.",
                    codigo="SIN_ACTIVIDAD",
                )
            hallazgo = accion.ciclo.hallazgo
            if HistorialHallazgo.objects.filter(
                accion_relacionada=accion,
                accion__in=cls.EVENTOS_REPROGRAMACION_NO_REPETIBLES,
                metadata_json__solicitud_id=solicitud.pk,
            ).exists():
                return ResultadoCorreo(aceptado=False, duplicado=True)
            intento = HistorialHallazgo.objects.create(
                hallazgo=hallazgo,
                usuario=usuario,
                accion="CORREO_REPROGRAMACION_INICIADO",
                accion_relacionada=accion,
                estado_anterior=hallazgo.estado,
                estado_nuevo=hallazgo.estado,
                comentario=f"Inicio del aviso de reprogramación para {accion.codigo}.",
                metadata_json={
                    "accion": accion.codigo,
                    "solicitud_id": solicitud.pk,
                },
            )

        try:
            mensaje, destinatarios = cls.construir_mensaje_reprogramacion(solicitud)
            codigo = cls._enviar_sendmail(mensaje, destinatarios)
        except CorreoCompromisoError as error:
            intento.accion = (
                "CORREO_REPROGRAMACION_INCIERTO"
                if error.incierto
                else "CORREO_REPROGRAMACION_FALLIDO"
            )
            intento.comentario = str(error)
            intento.metadata_json = {
                "accion": accion.codigo,
                "solicitud_id": solicitud.pk,
                "resultado": error.codigo,
            }
            intento.save(update_fields=["accion", "comentario", "metadata_json"])
            raise

        metadata = dict(solicitud.metadata_json or {})
        intento.accion = "CORREO_REPROGRAMACION_ACEPTADO"
        intento.comentario = (
            "sendmail aceptó el aviso de reprogramación. Esto no confirma la "
            "entrega final en el buzón."
        )
        intento.metadata_json = {
            "accion": accion.codigo,
            "solicitud_id": solicitud.pk,
            "aprobador_id": metadata.get("aprobador_id"),
            "codigo_salida": codigo,
        }
        intento.save(update_fields=["accion", "comentario", "metadata_json"])
        return ResultadoCorreo(aceptado=True, codigo_salida=codigo)
