from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Organización", {"fields": ("area", "cargo", "corporate_identifier")}),)
    list_display = UserAdmin.list_display + ("cargo", "area")
