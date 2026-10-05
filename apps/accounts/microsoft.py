"""Inicio de sesión corporativo con Microsoft Entra ID y Microsoft Graph.

El portal solicita únicamente el perfil básico y no persiste tokens de Microsoft.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction

from .models import Usuario


SCOPES = "User.Read"
GRAPH_PROFILE_URL = (
    "https://graph.microsoft.com/v1.0/me"
    "?$select=id,displayName,givenName,surname,mail,userPrincipalName,jobTitle,department"
)


class MicrosoftLoginError(Exception):
    """Error controlado del proveedor de identidad."""


@dataclass(frozen=True)
class MicrosoftConfig:
    tenant_id: str
    client_id: str
    client_secret: str

    @property
    def authority(self) -> str:
        tenant = quote(self.tenant_id, safe="")
        return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"


def get_config() -> MicrosoftConfig:
    if not settings.MICROSOFT_SSO_ENABLED:
        raise ImproperlyConfigured("El inicio de sesión con Microsoft no está habilitado.")
    config = MicrosoftConfig(
        tenant_id=settings.MICROSOFT_TENANT_ID.strip(),
        client_id=settings.MICROSOFT_CLIENT_ID.strip(),
        client_secret=settings.MICROSOFT_CLIENT_SECRET.strip(),
    )
    if not all((config.tenant_id, config.client_id, config.client_secret)):
        raise ImproperlyConfigured("La configuración de Microsoft Entra ID está incompleta.")
    return config


def create_authorization(request, redirect_uri: str) -> str:
    """Crea estado y PKCE, y devuelve la URL de autorización."""
    config = get_config()
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    request.session["microsoft_oauth"] = {
        "state": state,
        "code_verifier": verifier,
        "redirect_uri": redirect_uri,
    }
    params = urlencode({
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "prompt": "select_account",
    })
    return f"{config.authority}/authorize?{params}"


def exchange_code(code: str, redirect_uri: str, code_verifier: str) -> dict:
    config = get_config()
    return _request_json(
        f"{config.authority}/token",
        method="POST",
        data=urlencode({
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
            "scope": SCOPES,
        }).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


def fetch_profile(access_token: str) -> dict:
    if not access_token:
        raise MicrosoftLoginError("Microsoft no entregó un token de acceso válido.")
    profile = _request_json(
        GRAPH_PROFILE_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not profile.get("id"):
        raise MicrosoftLoginError("Microsoft no devolvió un identificador de usuario.")
    return profile


def _request_json(url: str, *, method: str = "GET", data: bytes | None = None, headers=None) -> dict:
    request = Request(url, data=data, method=method, headers=headers or {})
    try:
        with urlopen(request, timeout=10) as response:  # noqa: S310 - destinos fijos de Microsoft
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise MicrosoftLoginError("No se pudo completar la comunicación con Microsoft.") from exc


def _profile_names(profile: dict) -> tuple[str, str]:
    first_name = (profile.get("givenName") or "").strip()
    last_name = (profile.get("surname") or "").strip()
    display_name = (profile.get("displayName") or "").strip()
    if not first_name and not last_name and display_name:
        parts = display_name.rsplit(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) == 2 else ""
    return first_name[:150], last_name[:150]


def _unique_username(preferred: str, microsoft_id: str) -> str:
    base = (preferred or f"microsoft-{microsoft_id}")[:150]
    if not Usuario.objects.filter(username=base).exists():
        return base
    suffix = f"-ms-{microsoft_id[-8:]}"
    candidate = f"{base[:150-len(suffix)]}{suffix}"
    counter = 2
    while Usuario.objects.filter(username=candidate).exists():
        numbered = f"-{counter}"
        candidate = f"{base[:150-len(suffix)-len(numbered)]}{suffix}{numbered}"
        counter += 1
    return candidate


@transaction.atomic
def sync_user(profile: dict) -> Usuario:
    """Vincula o crea el usuario y actualiza el perfil corporativo."""
    config = get_config()
    microsoft_id = str(profile["id"]).strip()
    corporate_identifier = f"microsoft:{config.tenant_id}:{microsoft_id}"
    email = (profile.get("mail") or profile.get("userPrincipalName") or "").strip().lower()
    principal_name = (profile.get("userPrincipalName") or email).strip()

    user = Usuario.objects.select_for_update().filter(
        corporate_identifier=corporate_identifier
    ).first()
    if user is None and email:
        matches = list(
            Usuario.objects.select_for_update().filter(
                email__iexact=email, corporate_identifier__isnull=True
            )[:2]
        )
        if len(matches) > 1:
            raise MicrosoftLoginError(
                "Hay más de una cuenta local con el correo corporativo. Contacta al administrador."
            )
        user = matches[0] if matches else None

    created = user is None
    if created:
        user = Usuario(
            username=_unique_username(principal_name, microsoft_id),
            corporate_identifier=corporate_identifier,
            is_active=True,
        )
        user.set_unusable_password()
    elif not user.is_active:
        raise MicrosoftLoginError("La cuenta del portal está desactivada. Contacta al administrador.")

    first_name, last_name = _profile_names(profile)
    user.corporate_identifier = corporate_identifier
    user.first_name = first_name
    user.last_name = last_name
    user.email = email
    user.cargo = (profile.get("jobTitle") or "").strip()[:150]
    user.area = (profile.get("department") or "").strip()[:150]
    user.save()

    if created:
        user.add_role("USUARIO")
    return user
