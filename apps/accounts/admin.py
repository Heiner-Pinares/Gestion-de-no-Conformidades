from django.contrib import admin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("username", "email", "cargo", "area", "gerencia", "direccion", "jefe", "is_active")
    list_filter = ("is_active", "is_staff", "is_superuser", "direccion", "gerencia")
    search_fields = ("username", "first_name", "last_name", "email", "area", "gerencia", "direccion")
