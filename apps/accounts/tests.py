from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from django.contrib.auth.models import Group
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
        self.assertTrue(user.groups.filter(name="USUARIO").exists())
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
