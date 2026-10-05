from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import Usuario

ROLES = [("USUARIO", "Usuario"), ("VALIDADOR", "Validador"), ("ADMINISTRADOR", "Administrador")]


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
        if self.instance.pk:
            self.fields["roles"].initial = self.instance.roles
