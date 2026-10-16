from datetime import timedelta
from email import policy
from email.parser import BytesParser
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import paramiko
from django.contrib.messages import get_messages
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.catalogos.models import (
    Catalogo,
    FuenteDeteccion,
    Proceso,
    TipoRegistro,
    Urgencia,
)
from apps.hallazgos.models import HistorialHallazgo
from apps.hallazgos.services import AccionService, HallazgoService
from apps.hallazgos.services.correo_compromisos import (
    CorreoCompromisoError,
    CorreoCompromisoService,
    ResultadoCorreo,
)


CONFIG_CORREO = {
    "CORREO_COMPROMISOS_ENABLED": True,
    "CORREO_SSH_HOST": "correo.interno.example",
    "CORREO_SSH_PORT": 22,
    "CORREO_SSH_USER": "usuario-ssh",
    "CORREO_SSH_PASSWORD": "secreto-solo-test",
    "CORREO_SSH_TIMEOUT": 10,
    "CORREO_REMITENTE_NOMBRE": "Portal Claro - Gestión de No Conformidades",
    "CORREO_REMITENTE_EMAIL": "portal-nc@claro.com.pe",
    "PORTAL_PUBLIC_URL": "http://portal.example:8000",
}


@override_settings(**CONFIG_CORREO)
class CorreoCompromisoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_initial_data", stdout=StringIO())
        cls.jefe = Usuario.objects.create_user(
            "jefa.responsable",
            password="ClaveSoloParaTests-2026!",
            first_name="Rosa",
            last_name="Jefa",
            email="rosa.jefa@claro.com.pe",
        )
        cls.responsable = Usuario.objects.create_user(
            "ana.responsable",
            password="ClaveSoloParaTests-2026!",
            first_name="Ana",
            last_name="Responsable",
            email="ana.responsable@claro.com.pe",
            jefe=cls.jefe,
        )
        cls.responsable.add_role("USUARIO")
        cls.proceso = Proceso.objects.create(
            nombre="Proceso con correo", responsable=cls.responsable
        )
        cls.hallazgo = HallazgoService.crear(
            usuario=cls.responsable,
            borrador=False,
            datos={
                "titulo": "Hallazgo para notificación",
                "tipo_registro": TipoRegistro.objects.get(codigo="INC"),
                "fuente_deteccion": FuenteDeteccion.objects.get(codigo="OPERACION"),
                "proceso": cls.proceso,
                "responsable": cls.responsable,
                "descripcion": "Desviación que requiere un compromiso",
                "fecha_deteccion": timezone.now(),
                "fecha_solucion": timezone.localdate() + timedelta(days=10),
                "impacto_clientes": 1,
                "impacto_tiempo": 1,
                "impacto_soles": 1,
                "urgencia": Urgencia.objects.get(valor=1),
                "es_critica": "NO",
                "criterio_categoria": "Caso no crítico",
                "requisito_referencia": "Procedimiento de prueba",
            },
        )
        cls.accion = AccionService.crear(
            usuario=cls.responsable,
            hallazgo=cls.hallazgo,
            datos={
                "tipo": "INMEDIATA",
                "descripcion": "Restablecer la condición observada",
                "responsable": cls.responsable,
                "fecha_inicio": timezone.localdate(),
                "fet_inicial": timezone.localdate() + timedelta(days=2),
                "estado": "PENDIENTE",
                "resultado_esperado": "Condición restablecida",
                "comentario": "",
            },
        )

    def setUp(self):
        self.temporal = TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.known_hosts = Path(self.temporal.name) / "correo_known_hosts"
        self.ajuste_known_hosts = override_settings(
            CORREO_SSH_KNOWN_HOSTS=str(self.known_hosts)
        )
        self.ajuste_known_hosts.enable()
        self.addCleanup(self.ajuste_known_hosts.disable)

    @staticmethod
    def cliente_ssh(*, codigo=0, detalle=b""):
        cliente = MagicMock()
        entrada = MagicMock()
        salida = MagicMock()
        errores = MagicMock()
        salida.channel.recv_exit_status.return_value = codigo
        errores.read.return_value = detalle
        cliente.exec_command.return_value = entrada, salida, errores
        return cliente, entrada, salida

    def test_envia_mime_html_al_responsable_y_copia_al_jefe(self):
        cliente, entrada, _ = self.cliente_ssh()
        with patch(
            "apps.hallazgos.services.correo_compromisos.paramiko.SSHClient",
            return_value=cliente,
        ) as crear_cliente:
            resultado = CorreoCompromisoService.enviar_asignacion(
                accion=self.accion,
                usuario=self.responsable,
            )

        self.assertTrue(resultado.aceptado)
        self.assertFalse(resultado.duplicado)
        crear_cliente.assert_called_once_with()
        cliente.connect.assert_called_once_with(
            hostname="correo.interno.example",
            port=22,
            username="usuario-ssh",
            password="secreto-solo-test",
            timeout=10,
            banner_timeout=10,
            auth_timeout=10,
            allow_agent=False,
            look_for_keys=False,
        )
        comando = cliente.exec_command.call_args.args[0]
        self.assertEqual(
            comando,
            "sendmail -i ana.responsable@claro.com.pe rosa.jefa@claro.com.pe",
        )
        mensaje = BytesParser(policy=policy.default).parsebytes(
            entrada.write.call_args.args[0]
        )
        self.assertEqual(mensaje["To"], "ana.responsable@claro.com.pe")
        self.assertEqual(mensaje["Cc"], "rosa.jefa@claro.com.pe")
        self.assertEqual(mensaje["Subject"], f"Nuevo compromiso asignado: {self.accion.codigo}")
        self.assertIn("Restablecer la condición observada", mensaje.get_body(("plain",)).get_content())
        html = mensaje.get_body(("html",)).get_content()
        self.assertIn("Nuevo compromiso asignado", html)
        self.assertIn(self.hallazgo.codigo, html)
        self.assertIn(self.accion.codigo, html)
        self.assertIn("http://portal.example:8000", html)
        entrada.channel.shutdown_write.assert_called_once_with()
        cliente.close.assert_called_once_with()
        self.assertTrue(self.known_hosts.exists())
        self.assertTrue(
            HistorialHallazgo.objects.filter(
                accion_relacionada=self.accion,
                accion="CORREO_COMPROMISO_ACEPTADO",
            ).exists()
        )

    def test_agrega_destinatarios_configurados_sin_reemplazar_responsable_y_jefe(self):
        Catalogo.objects.create(
            clase="CATEGORIA",
            codigo="CFG_MAIL_TO_000000000000000001",
            nombre="calidad@claro.com.pe",
            activo=True,
        )
        Catalogo.objects.create(
            clase="CATEGORIA",
            codigo="CFG_MAIL_CC_000000000000000001",
            nombre="auditoria@claro.com.pe",
            activo=True,
        )
        Catalogo.objects.create(
            clase="CATEGORIA",
            codigo="CFG_MAIL_CC_000000000000000002",
            nombre="inactivo@claro.com.pe",
            activo=False,
        )
        # Si un correo está en To y CC, To tiene precedencia y no se duplica.
        Catalogo.objects.create(
            clase="CATEGORIA",
            codigo="CFG_MAIL_CC_000000000000000003",
            nombre="calidad@claro.com.pe",
            activo=True,
        )

        mensaje, destinatarios = CorreoCompromisoService.construir_mensaje(self.accion)

        self.assertEqual(
            mensaje["To"],
            "ana.responsable@claro.com.pe, calidad@claro.com.pe",
        )
        self.assertEqual(
            mensaje["Cc"],
            "rosa.jefa@claro.com.pe, auditoria@claro.com.pe",
        )
        self.assertEqual(destinatarios, [
            "ana.responsable@claro.com.pe",
            "calidad@claro.com.pe",
            "rosa.jefa@claro.com.pe",
            "auditoria@claro.com.pe",
        ])

    def test_no_repite_un_correo_ya_aceptado(self):
        cliente, _, _ = self.cliente_ssh()
        with patch(
            "apps.hallazgos.services.correo_compromisos.paramiko.SSHClient",
            return_value=cliente,
        ):
            primero = CorreoCompromisoService.enviar_asignacion(
                accion=self.accion, usuario=self.responsable
            )
            segundo = CorreoCompromisoService.enviar_asignacion(
                accion=self.accion, usuario=self.responsable
            )
        self.assertTrue(primero.aceptado)
        self.assertTrue(segundo.duplicado)
        self.assertEqual(cliente.exec_command.call_count, 1)

    def test_reprogramacion_notifica_al_aprobador_con_el_html_solicitado(self):
        propuesta = timezone.localdate() + timedelta(days=5)
        solicitud = AccionService.solicitar_reprogramacion(
            usuario=self.responsable,
            accion=self.accion,
            nueva_fecha=propuesta,
            motivo="Se requiere tiempo adicional para completar la validación.",
            aprobador=self.jefe,
        )
        cliente, entrada, _ = self.cliente_ssh()
        with patch(
            "apps.hallazgos.services.correo_compromisos.paramiko.SSHClient",
            return_value=cliente,
        ):
            resultado = CorreoCompromisoService.enviar_reprogramacion(
                solicitud=solicitud,
                usuario=self.responsable,
            )

        self.assertTrue(resultado.aceptado)
        self.assertEqual(
            cliente.exec_command.call_args.args[0],
            "sendmail -i rosa.jefa@claro.com.pe ana.responsable@claro.com.pe",
        )
        mensaje = BytesParser(policy=policy.default).parsebytes(
            entrada.write.call_args.args[0]
        )
        self.assertEqual(mensaje["To"], "rosa.jefa@claro.com.pe")
        self.assertEqual(mensaje["Cc"], "ana.responsable@claro.com.pe")
        self.assertEqual(
            mensaje["Subject"],
            f"Reprogramación pendiente de aprobación: {self.accion.codigo}",
        )
        html = mensaje.get_body(("html",)).get_content()
        self.assertIn("Recordatorio de reprogramación", html)
        self.assertIn("Rosa Jefa", html)
        self.assertIn(self.hallazgo.codigo, html)
        self.assertIn(self.accion.codigo, html)
        self.assertIn(propuesta.strftime("%d/%m/%Y"), html)
        self.assertIn("Se requiere tiempo adicional", html)
        self.assertIn("http://portal.example:8000", html)
        self.assertTrue(
            HistorialHallazgo.objects.filter(
                accion_relacionada=self.accion,
                accion="CORREO_REPROGRAMACION_ACEPTADO",
                metadata_json__solicitud_id=solicitud.pk,
            ).exists()
        )

    def test_reprogramacion_aceptada_no_se_envia_dos_veces(self):
        solicitud = AccionService.solicitar_reprogramacion(
            usuario=self.responsable,
            accion=self.accion,
            nueva_fecha=timezone.localdate() + timedelta(days=5),
            motivo="Reprogramación controlada.",
            aprobador=self.jefe,
        )
        cliente, _, _ = self.cliente_ssh()
        with patch(
            "apps.hallazgos.services.correo_compromisos.paramiko.SSHClient",
            return_value=cliente,
        ):
            primero = CorreoCompromisoService.enviar_reprogramacion(
                solicitud=solicitud, usuario=self.responsable
            )
            segundo = CorreoCompromisoService.enviar_reprogramacion(
                solicitud=solicitud, usuario=self.responsable
            )

        self.assertTrue(primero.aceptado)
        self.assertTrue(segundo.duplicado)
        self.assertEqual(cliente.exec_command.call_count, 1)

    def test_solicitud_se_conserva_si_el_correo_al_jefe_falla(self):
        self.client.force_login(self.responsable)
        with patch(
            "apps.hallazgos.views.CorreoCompromisoService.enviar_reprogramacion",
            side_effect=CorreoCompromisoError(
                "No se pudo acceder al servidor de correo.",
                codigo="SSH_INACCESIBLE",
            ),
        ) as enviar:
            respuesta = self.client.post(
                reverse("accion_reprogramar", args=[self.accion.pk]),
                {
                    "nueva_fecha": (
                        timezone.localdate() + timedelta(days=5)
                    ).isoformat(),
                    "motivo": "Se requiere ampliar el plazo de validación.",
                    "aprobador": self.jefe.pk,
                },
            )

        self.assertRedirects(
            respuesta,
            reverse("hallazgo_detalle", args=[self.hallazgo.pk]),
            fetch_redirect_response=False,
        )
        solicitud = HistorialHallazgo.objects.get(
            accion_relacionada=self.accion,
            accion="SOLICITUD_REPROGRAMACION",
        )
        self.assertEqual(solicitud.metadata_json["estado"], "PENDIENTE")
        self.assertEqual(solicitud.metadata_json["aprobador_id"], self.jefe.pk)
        enviar.assert_called_once_with(
            solicitud=solicitud,
            usuario=self.responsable,
        )
        mensajes = [str(mensaje) for mensaje in get_messages(respuesta.wsgi_request)]
        self.assertTrue(any("quedó registrada" in mensaje for mensaje in mensajes))

    def test_registra_credenciales_ssh_rechazadas_sin_exponerlas(self):
        cliente, _, _ = self.cliente_ssh()
        cliente.connect.side_effect = paramiko.AuthenticationException()
        with patch(
            "apps.hallazgos.services.correo_compromisos.paramiko.SSHClient",
            return_value=cliente,
        ), self.assertRaisesRegex(CorreoCompromisoError, "rechazó las credenciales"):
            CorreoCompromisoService.enviar_asignacion(
                accion=self.accion, usuario=self.responsable
            )
        evento = HistorialHallazgo.objects.get(
            accion_relacionada=self.accion,
            accion="CORREO_COMPROMISO_FALLIDO",
        )
        self.assertEqual(evento.metadata_json["resultado"], "SSH_AUTENTICACION")
        self.assertNotIn("secreto-solo-test", evento.comentario)
        cliente.close.assert_called_once_with()

    def test_rechazo_de_sendmail_no_se_considera_aceptado(self):
        cliente, _, _ = self.cliente_ssh(codigo=75, detalle=b"temporal failure")
        with patch(
            "apps.hallazgos.services.correo_compromisos.paramiko.SSHClient",
            return_value=cliente,
        ), self.assertRaisesRegex(CorreoCompromisoError, "código 75"):
            CorreoCompromisoService.enviar_asignacion(
                accion=self.accion, usuario=self.responsable
            )
        evento = HistorialHallazgo.objects.get(
            accion_relacionada=self.accion,
            accion="CORREO_COMPROMISO_FALLIDO",
        )
        self.assertEqual(evento.metadata_json["resultado"], "SENDMAIL_RECHAZADO")

    def test_bloquea_direccion_invalida_antes_de_abrir_ssh(self):
        Usuario.objects.filter(pk=self.responsable.pk).update(email="direccion-invalida")
        with patch(
            "apps.hallazgos.services.correo_compromisos.paramiko.SSHClient"
        ) as crear_cliente, self.assertRaisesRegex(
            CorreoCompromisoError, "dirección de correo no válida"
        ):
            CorreoCompromisoService.enviar_asignacion(
                accion=self.accion, usuario=self.responsable
            )
        crear_cliente.assert_not_called()

    @override_settings(CORREO_SSH_PASSWORD="")
    def test_falta_de_secreto_detiene_el_envio_con_mensaje_claro(self):
        with patch(
            "apps.hallazgos.services.correo_compromisos.paramiko.SSHClient"
        ) as crear_cliente, self.assertRaisesRegex(
            CorreoCompromisoError, "CORREO_SSH_PASSWORD"
        ):
            CorreoCompromisoService.enviar_asignacion(
                accion=self.accion, usuario=self.responsable
            )
        crear_cliente.assert_not_called()

    def test_guardar_plan_invoca_el_correo_solo_para_la_nueva_actividad(self):
        self.client.force_login(self.responsable)
        plan = {
            "actividades-TOTAL_FORMS": "1",
            "actividades-INITIAL_FORMS": "0",
            "actividades-MIN_NUM_FORMS": "1",
            "actividades-MAX_NUM_FORMS": "1000",
            "actividades-0-tipo": "CORRECTIVA",
            "actividades-0-descripcion": "Prevenir la recurrencia",
            "actividades-0-responsable": str(self.responsable.pk),
            "actividades-0-fet_inicial": (
                timezone.localdate() + timedelta(days=3)
            ).isoformat(),
            "actividades-0-estado": "PENDIENTE",
        }
        with patch(
            "apps.hallazgos.views.CorreoCompromisoService.enviar_asignacion",
            return_value=ResultadoCorreo(aceptado=True, codigo_salida=0),
        ) as enviar:
            respuesta = self.client.post(
                reverse("hallazgo_accion", args=[self.hallazgo.pk]), plan
            )
        self.assertRedirects(
            respuesta,
            reverse("hallazgo_acciones_creadas", args=[self.hallazgo.pk]),
            fetch_redirect_response=False,
        )
        enviar.assert_called_once()
        nueva = enviar.call_args.kwargs["accion"]
        self.assertEqual(nueva.descripcion, "Prevenir la recurrencia")
        self.assertEqual(enviar.call_args.kwargs["usuario"], self.responsable)

    def test_guardado_exige_autenticacion_y_csrf_antes_del_envio(self):
        url = reverse("hallazgo_accion", args=[self.hallazgo.pk])
        datos = {
            "actividades-TOTAL_FORMS": "1",
            "actividades-INITIAL_FORMS": "0",
            "actividades-MIN_NUM_FORMS": "1",
            "actividades-MAX_NUM_FORMS": "1000",
            "actividades-0-tipo": "CORRECTIVA",
            "actividades-0-descripcion": "Actividad protegida",
            "actividades-0-responsable": str(self.responsable.pk),
            "actividades-0-fet_inicial": (
                timezone.localdate() + timedelta(days=3)
            ).isoformat(),
            "actividades-0-estado": "PENDIENTE",
        }
        with patch(
            "apps.hallazgos.views.CorreoCompromisoService.enviar_asignacion"
        ) as enviar:
            self.assertEqual(self.client.post(url, datos).status_code, 302)
            cliente_csrf = Client(enforce_csrf_checks=True)
            cliente_csrf.force_login(self.responsable)
            self.assertEqual(cliente_csrf.post(url, datos).status_code, 403)
        enviar.assert_not_called()
