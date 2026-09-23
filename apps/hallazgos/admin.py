"""El admin técnico consulta; nunca sustituye al workflow ni edita la auditoría."""
from django.contrib import admin
from . import models


class SoloConsultaAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.has_perm("accounts.ver_todos_hallazgos")


@admin.register(models.Hallazgo)
class HallazgoAdmin(SoloConsultaAdmin):
    list_display = ["codigo", "titulo", "estado", "responsable", "fecha_registro"]
    list_filter = ["estado", "tipo_registro", "es_critica"]
    search_fields = ["codigo", "titulo"]
    list_select_related = ["responsable"]


for modelo in (models.CicloTratamiento, models.Accion, models.PBI, models.EvaluacionEficacia,
    models.ComunicacionHallazgo, models.HistorialHallazgo, models.Notificacion, models.CorrelativoSAC):
    admin.site.register(modelo, SoloConsultaAdmin)
# Evidencias nunca expone archivo.url en el admin. Descarga solo por view autorizada.
