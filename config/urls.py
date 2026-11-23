from django.conf import settings
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path(
        "favicon.ico",
        RedirectView.as_view(
            url=f"{settings.STATIC_URL.rstrip('/')}/images/favicon-nc.ico",
            permanent=True,
        ),
        name="favicon",
    ),
    path("cuentas/", include("apps.accounts.urls")),
    path("administracion/", include("apps.catalogos.urls")),
    path("admin-tecnico/", RedirectView.as_view(pattern_name="inicio", permanent=False)),
    path("", include("apps.hallazgos.urls")),
]
