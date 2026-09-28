import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import LoginView
from django.core.exceptions import ImproperlyConfigured
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET

from .forms import AccesoForm
from .microsoft import (
    MicrosoftLoginError, create_authorization, exchange_code, fetch_profile, sync_user,
)

logger = logging.getLogger(__name__)


class AccesoView(LoginView):
    authentication_form = AccesoForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.set_expiry(60 * 60 * 24 * 14 if form.cleaned_data.get("recordarme") else 0)
        return response


def _microsoft_redirect_uri(request):
    configured = settings.MICROSOFT_REDIRECT_URI.strip()
    return configured or request.build_absolute_uri(reverse("microsoft_callback"))


@require_GET
def microsoft_start(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    next_url = request.GET.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        request.session["microsoft_next"] = next_url
    try:
        return redirect(create_authorization(request, _microsoft_redirect_uri(request)))
    except ImproperlyConfigured:
        messages.error(
            request,
            "El ingreso con Microsoft todavía no está configurado. Puedes usar tu cuenta local.",
        )
        return redirect("login")


@require_GET
def microsoft_callback(request):
    oauth = request.session.pop("microsoft_oauth", {})
    expected_state = oauth.get("state", "")
    received_state = request.GET.get("state", "")
    if not expected_state or not received_state or not secrets.compare_digest(expected_state, received_state):
        messages.error(request, "La respuesta de Microsoft no pudo validarse. Intenta ingresar nuevamente.")
        return redirect("login")
    if request.GET.get("error"):
        messages.error(request, "El ingreso con Microsoft fue cancelado o no fue autorizado.")
        return redirect("login")
    code = request.GET.get("code", "")
    if not code:
        messages.error(request, "Microsoft no devolvió el código necesario para iniciar sesión.")
        return redirect("login")

    try:
        token_data = exchange_code(code, oauth["redirect_uri"], oauth["code_verifier"])
        user = sync_user(fetch_profile(token_data.get("access_token", "")))
    except (ImproperlyConfigured, MicrosoftLoginError, KeyError) as exc:
        logger.exception("Falló el inicio de sesión corporativo con Microsoft: %s", exc)
        messages.error(request, "No se pudo iniciar sesión con Microsoft. Contacta al administrador.")
        return redirect("login")

    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session.set_expiry(0)
    destination = request.session.pop("microsoft_next", "")
    if destination and url_has_allowed_host_and_scheme(destination, allowed_hosts={request.get_host()}):
        return redirect(destination)
    return redirect(settings.LOGIN_REDIRECT_URL)
