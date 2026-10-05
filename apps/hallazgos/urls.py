from django.urls import path
from . import views
from .registro_views import registro_general
urlpatterns = [
    path("registro-general/", registro_general, name="registro_general"),
    path("", views.inicio, name="inicio"),
    path("ayuda/", views.ayuda, name="ayuda"),
    path("hallazgos/nuevo/", views.hallazgo_crear, name="hallazgo_crear"),
    path("hallazgos/", views.hallazgo_buscar, name="hallazgo_buscar"),
    path("administracion/validaciones/", views.validaciones_admin, name="validaciones_admin"),
    path("hallazgos/<int:pk>/", views.hallazgo_detalle, name="hallazgo_detalle"),
    path("hallazgos/<int:pk>/editar/", views.hallazgo_editar, name="hallazgo_editar"),
    path("hallazgos/<int:pk>/transicion/<str:accion>/", views.hallazgo_transicion, name="hallazgo_transicion"),
    path("hallazgos/<int:pk>/causa/", views.hallazgo_causa, name="hallazgo_causa"),
    path("hallazgos/<int:pk>/acciones/nueva/", views.hallazgo_accion, name="hallazgo_accion"),
    path("hallazgos/<int:pk>/acciones/guardadas/", views.hallazgo_acciones_creadas, name="hallazgo_acciones_creadas"),
    path("hallazgos/<int:pk>/acciones/seguimiento/", views.hallazgo_acciones_seguimiento, name="hallazgo_acciones_seguimiento"),
    path("acciones/<int:pk>/seguimiento/", views.accion_seguimiento, name="accion_seguimiento"),
    path("acciones/<int:pk>/reprogramar/", views.accion_reprogramar, name="accion_reprogramar"),
    path("reprogramaciones/<int:pk>/<str:decision>/", views.accion_reprogramacion_resolver, name="accion_reprogramacion_resolver"),
    path("hallazgos/<int:pk>/eficacia/", views.hallazgo_eficacia, name="hallazgo_eficacia"),
    path("hallazgos/<int:pk>/pbi/", views.hallazgo_pbi, name="hallazgo_pbi"),
    path("hallazgos/<int:pk>/comunicacion/", views.hallazgo_comunicacion, name="hallazgo_comunicacion"),
    path("hallazgos/<int:pk>/evidencias/", views.hallazgo_evidencia, name="hallazgo_evidencia"),
    path("evidencias/<int:pk>/descargar/", views.evidencia_descargar, name="evidencia_descargar"),
    path("notificaciones/", views.notificaciones, name="notificaciones"),
    path("notificaciones/<int:pk>/leer/", views.notificacion_leer, name="notificacion_leer"),
]
