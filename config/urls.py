from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("cuentas/", include("apps.accounts.urls")),
    path("administracion/", include("apps.catalogos.urls")),
    path("admin-tecnico/", admin.site.urls),
    path("", include("apps.hallazgos.urls")),
]
