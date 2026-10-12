from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import ROLES, Usuario


def configurar_procesos_validacion(formulario):
    """Muestra en el usuario los procesos que podrá revisar como Validador."""
    from apps.catalogos.models import Proceso, ProcesoValidador

    formulario.fields["procesos_validacion"] = forms.ModelMultipleChoiceField(
        label="Procesos que valida",
        queryset=Proceso.objects.filter(activo=True).order_by("nombre"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            "Obligatorio para un Validador activo. Solo verá los hallazgos "
            "enviados a verificación de estos procesos."
        ),
    )
    if formulario.instance and formulario.instance.pk:
        formulario.fields["procesos_validacion"].initial = Proceso.objects.filter(
            pk__in=ProcesoValidador.objects.filter(
                usuario_id=formulario.instance.pk,
            ).values("proceso_id"),
        )


def validar_procesos_validacion(formulario, datos):
    roles = set(datos.get("roles") or [])
    procesos = datos.get("procesos_validacion")
    usuario_activo = datos.get("is_active", True)
    if "VALIDADOR" not in roles and procesos:
        formulario.add_error(
            "procesos_validacion",
            "Seleccione el rol Validador para asignar procesos.",
        )
    elif "VALIDADOR" in roles and usuario_activo and not procesos:
        formulario.add_error(
            "procesos_validacion",
            "Seleccione al menos un proceso para que el Validador reciba hallazgos.",
        )
    return datos


class AccesoForm(AuthenticationForm):
    username = forms.CharField(label="Usuario de acceso", widget=forms.TextInput(attrs={"class": "input", "autocomplete": "username"}))
    password = forms.CharField(label="Contraseña", strip=False, widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "current-password"}))
    recordarme = forms.BooleanField(label="Recordarme", required=False)


class UsuarioCreacionForm(UserCreationForm):
    roles = forms.MultipleChoiceField(choices=ROLES, widget=forms.CheckboxSelectMultiple)

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = (
            "username", "first_name", "last_name", "email", "area", "gerencia",
            "direccion", "cargo", "jefe",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configurar_procesos_validacion(self)

    def clean(self):
        return validar_procesos_validacion(self, super().clean())


class UsuarioEdicionForm(forms.ModelForm):
    roles = forms.MultipleChoiceField(choices=ROLES, widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Usuario
        fields = (
            "first_name", "last_name", "email", "area", "gerencia", "direccion",
            "cargo", "jefe", "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configurar_procesos_validacion(self)
        if self.instance.pk:
            self.fields["roles"].initial = self.instance.roles

    def clean(self):
        return validar_procesos_validacion(self, super().clean())
