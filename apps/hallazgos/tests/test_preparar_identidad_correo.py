from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import paramiko
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase, override_settings


@override_settings(
    CORREO_COMPROMISOS_ENABLED=True,
    CORREO_SSH_HOST="correo.interno.example",
    CORREO_SSH_PORT=22,
    CORREO_SSH_TIMEOUT=10,
)
class PrepararIdentidadCorreoTests(SimpleTestCase):
    def setUp(self):
        self.temporal = TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.destino = Path(self.temporal.name) / "correo_known_hosts"

    @staticmethod
    def _transporte_con(clave):
        transporte = MagicMock()
        transporte.get_remote_server_key.return_value = clave
        return transporte

    def test_guarda_clave_publica_en_formato_known_hosts(self):
        clave = paramiko.RSAKey.generate(1024)
        transporte = self._transporte_con(clave)
        salida = StringIO()
        with patch(
            "apps.hallazgos.management.commands.preparar_identidad_correo.socket.create_connection",
            return_value=MagicMock(),
        ), patch(
            "apps.hallazgos.management.commands.preparar_identidad_correo.paramiko.Transport",
            return_value=transporte,
        ):
            call_command(
                "preparar_identidad_correo",
                archivo=str(self.destino),
                stdout=salida,
            )

        claves = paramiko.HostKeys(str(self.destino))
        guardada = claves.lookup("correo.interno.example")[clave.get_name()]
        self.assertEqual(guardada.asbytes(), clave.asbytes())
        self.assertIn("SHA256:", salida.getvalue())
        transporte.close.assert_called_once_with()

    def test_no_reemplaza_una_identidad_distinta(self):
        anterior = paramiko.RSAKey.generate(1024)
        nueva = paramiko.RSAKey.generate(1024)
        self.destino.write_text(
            f"correo.interno.example {anterior.get_name()} {anterior.get_base64()}\n",
            encoding="ascii",
        )
        transporte = self._transporte_con(nueva)
        with patch(
            "apps.hallazgos.management.commands.preparar_identidad_correo.socket.create_connection",
            return_value=MagicMock(),
        ), patch(
            "apps.hallazgos.management.commands.preparar_identidad_correo.paramiko.Transport",
            return_value=transporte,
        ), self.assertRaisesRegex(CommandError, "no coincide"):
            call_command("preparar_identidad_correo", archivo=str(self.destino))

        claves = paramiko.HostKeys(str(self.destino))
        guardada = claves.lookup("correo.interno.example")[anterior.get_name()]
        self.assertEqual(guardada.asbytes(), anterior.asbytes())
