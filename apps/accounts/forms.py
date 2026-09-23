from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import Group
from .models import Usuario


class AccesoForm(AuthenticationForm):
    username = forms.CharField(label="Usuario de acceso", widget=forms.TextInput(attrs={"class": "input", "autocomplete": "username"}))
    password = forms.CharField(label="Contraseña", strip=False, widget=forms.PasswordInput(attrs={"class": "input", "autocomplete": "current-password"}))
    recordarme = forms.BooleanField(label="Recordarme", required=False)


class UsuarioCreacionForm(UserCreationForm):
    roles = forms.ModelMultipleChoiceField(queryset=Group.objects.filter(name__in=["USUARIO", "VALIDADOR", "ADMINISTRADOR"]), widget=forms.CheckboxSelectMultiple)

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("username", "first_name", "last_name", "email", "area", "cargo")


class UsuarioEdicionForm(forms.ModelForm):
    roles = forms.ModelMultipleChoiceField(queryset=Group.objects.filter(name__in=["USUARIO", "VALIDADOR", "ADMINISTRADOR"]), widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email", "area", "cargo", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["roles"].initial = self.instance.groups.all()
