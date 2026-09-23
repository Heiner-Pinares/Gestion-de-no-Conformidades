from django.urls import path
from . import views
urlpatterns = [
    path("usuarios/", views.usuarios, name="usuarios"),
    path("usuarios/crear/", views.usuario_crear, name="usuario_crear"),
    path("usuarios/<int:pk>/", views.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:pk>/clave/", views.usuario_password, name="usuario_password"),
    path("catalogos/", views.catalogos, name="catalogos"),
    path("catalogos/<str:tipo>/nuevo/", views.catalogo_editar, name="catalogo_crear"),
    path("catalogos/<str:tipo>/<str:pk>/", views.catalogo_editar, name="catalogo_editar"),
    path("auditoria/", views.auditoria, name="auditoria"),
    path("reportes/", views.reportes, name="reportes"),
]
