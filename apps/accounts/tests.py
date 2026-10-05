from urllib.parse import parse_qs, urlparse
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Usuario


MICROSOFT_SETTINGS = {
    "MICROSOFT_SSO_ENABLED": True,
    "MICROSOFT_TENANT_ID": "tenant-corporativo",
    "MICROSOFT_CLIENT_ID": "cliente-portal",
    "MICROSOFT_CLIENT_SECRET": "secreto-de-prueba",
    "MICROSOFT_REDIRECT_URI": "http://testserver/cuentas/microsoft/callback/",
}


@override_settings(**MICROSOFT_SETTINGS)
class MicrosoftLoginTests(TestCase):
    def test_login_muestra_acceso_microsoft(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Ingresar con Microsoft")
        self.assertContains(response, reverse("microsoft_start"))
        self.assertContains(response, "login-user-symbol")
        self.assertNotContains(response, ">♙<")

    def test_inicio_crea_state_y_pkce(self):
        response = self.client.get(reverse("microsoft_start"), {"next": "/buscar/"})
        self.assertEqual(response.status_code, 302)
        parsed = urlparse(response.url)
        params = parse_qs(parsed.query)
        self.assertEqual(
            parsed.path,
            "/tenant-corporativo/oauth2/v2.0/authorize",
        )
        self.assertEqual(params["client_id"], ["cliente-portal"])
        self.assertEqual(params["response_type"], ["code"])
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertIn("User.Read", params["scope"][0])
        oauth = self.client.session["microsoft_oauth"]
        self.assertEqual(params["state"], [oauth["state"]])
        self.assertTrue(oauth["code_verifier"])
        self.assertEqual(self.client.session["microsoft_next"], "/buscar/")

    @patch("apps.accounts.views.fetch_profile")
    @patch("apps.accounts.views.exchange_code")
    def test_callback_crea_usuario_y_sincroniza_perfil(self, exchange_code, fetch_profile):
        exchange_code.return_value = {"access_token": "token-temporal"}
        fetch_profile.return_value = {
            "id": "abc-123",
            "displayName": "Ana Torres",
            "givenName": "Ana",
            "surname": "Torres",
            "mail": "ana.torres@empresa.com",
            "userPrincipalName": "ana.torres@empresa.com",
            "jobTitle": "Jefa de Calidad",
            "department": "Calidad y Procesos",
        }
        self.client.get(reverse("microsoft_start"))
        oauth = self.client.session["microsoft_oauth"]

        response = self.client.get(
            reverse("microsoft_callback"),
            {"state": oauth["state"], "code": "codigo-autorizacion"},
        )

        self.assertRedirects(response, reverse("inicio"))
        user = Usuario.objects.get(email="ana.torres@empresa.com")
        self.assertEqual(user.get_full_name(), "Ana Torres")
        self.assertEqual(user.cargo, "Jefa de Calidad")
        self.assertEqual(user.area, "Calidad y Procesos")
        self.assertEqual(
            user.corporate_identifier,
            "microsoft:tenant-corporativo:abc-123",
        )
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.has_role("USUARIO"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertNotIn("microsoft_oauth", self.client.session)
        self.assertNotIn("token-temporal", str(dict(self.client.session)))
        exchange_code.assert_called_once_with(
            "codigo-autorizacion",
            MICROSOFT_SETTINGS["MICROSOFT_REDIRECT_URI"],
            oauth["code_verifier"],
        )
        fetch_profile.assert_called_once_with("token-temporal")

    @patch("apps.accounts.views.exchange_code")
    def test_callback_rechaza_state_invalido(self, exchange_code):
        self.client.get(reverse("microsoft_start"))
        response = self.client.get(
            reverse("microsoft_callback"),
            {"state": "incorrecto", "code": "codigo"},
        )
        self.assertRedirects(response, reverse("login"))
        exchange_code.assert_not_called()
        self.assertFalse(Usuario.objects.exists())

    @patch("apps.accounts.views.fetch_profile")
    @patch("apps.accounts.views.exchange_code")
    def test_callback_vincula_cuenta_local_por_correo(self, exchange_code, fetch_profile):
        local = Usuario.objects.create_user(
            username="ana.local",
            email="ana@empresa.com",
            password="UnaClaveLocalSegura-123",
        )
        exchange_code.return_value = {"access_token": "token"}
        fetch_profile.return_value = {
            "id": "microsoft-ana",
            "displayName": "Ana Microsoft",
            "mail": "ana@empresa.com",
            "userPrincipalName": "ana@empresa.com",
            "jobTitle": "Analista",
            "department": "Operaciones",
        }
        self.client.get(reverse("microsoft_start"))
        oauth = self.client.session["microsoft_oauth"]
        self.client.get(
            reverse("microsoft_callback"),
            {"state": oauth["state"], "code": "codigo"},
        )
        local.refresh_from_db()
        self.assertEqual(Usuario.objects.count(), 1)
        self.assertEqual(local.corporate_identifier, "microsoft:tenant-corporativo:microsoft-ana")
        self.assertTrue(local.has_usable_password())


class MicrosoftDisabledTests(TestCase):
    @override_settings(
        MICROSOFT_SSO_ENABLED=False,
        MICROSOFT_TENANT_ID="",
        MICROSOFT_CLIENT_ID="",
        MICROSOFT_CLIENT_SECRET="",
    )
    def test_configuracion_incompleta_vuelve_al_login(self):
        response = self.client.get(reverse("microsoft_start"), follow=True)
        self.assertRedirects(response, reverse("login"))
        self.assertContains(response, "todavía no está configurado")


class ImportarUsuariosOperacionesTests(TestCase):
    @staticmethod
    def crear_xlsx(ruta):
        filas = [
            ["Cod. Comunicación", "Correo electrónico", "Jefe", "Nombre completo", "Área", "Gerencia", "Dirección"],
            ["C10001", "carlos1@claro.com.pe", "MARIA GOMEZ PEREZ", "CARLOS VICENTE FARFAN ACHAMISO", "Facturación", "Operaciones", "Operaciones Comerciales"],
            ["C10002", "carlos2@claro.com.pe", "MARIA GOMEZ PEREZ", "CARLOS EDUARDO FARFAN CASTRO", "Facturación", "Operaciones", "Operaciones Comerciales"],
            ["C10003", "maria.gomez@claro.com.pe", "", "MARIA GOMEZ PEREZ", "Operaciones", "Operaciones", "Operaciones Comerciales"],
        ]
        def celda(columna, fila, valor):
            return f'<c r="{columna}{fila}" t="inlineStr"><is><t>{valor}</t></is></c>'
        letras = "ABCDEFG"
        cuerpo = "".join(
            f'<row r="{numero}">{"".join(celda(letras[i], numero, valor) for i, valor in enumerate(valores))}</row>'
            for numero, valores in enumerate(filas, 1)
        )
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{cuerpo}</sheetData></worksheet>'
        )
        with ZipFile(ruta, "w") as archivo:
            archivo.writestr("xl/worksheets/sheet1.xml", xml)

    def test_importa_perfiles_claves_jefaturas_y_resuelve_usuario_duplicado(self):
        with TemporaryDirectory() as carpeta:
            ruta = Path(carpeta) / "usuarios.xlsx"
            self.crear_xlsx(ruta)
            salida = StringIO()
            call_command("importar_usuarios_operaciones", ruta, dry_run=True, stdout=salida)
            self.assertIn("3 usuarios", salida.getvalue())
            self.assertFalse(Usuario.objects.exists())

            call_command("importar_usuarios_operaciones", ruta, stdout=StringIO())

        self.assertEqual(Usuario.objects.count(), 3)
        primero = Usuario.objects.get(email="carlos1@claro.com.pe")
        segundo = Usuario.objects.get(email="carlos2@claro.com.pe")
        jefa = Usuario.objects.get(email="maria.gomez@claro.com.pe")
        self.assertEqual((primero.username, segundo.username, jefa.username), (
            "carlos.farfan", "carlos.farfan.2", "maria.gomez",
        ))
        self.assertTrue(primero.check_password("C10001"))
        self.assertTrue(segundo.check_password("C10002"))
        self.assertEqual(primero.roles, ["USUARIO"])
        self.assertEqual(primero.area, "Facturación")
        self.assertEqual(primero.gerencia, "Operaciones")
        self.assertEqual(primero.direccion, "Operaciones Comerciales")
        self.assertEqual(primero.jefe, jefa)
        self.assertEqual(jefa.cargo, "Jefe")
