from django import forms
from apps.accounts.models import UsuarioRol
from .models import (
    CategoriaCausa, ConfiguracionImpacto, ConfiguracionUrgencia, FuenteDeteccion, Impacto, MatrizPrioridad, PreguntaCausa,
    Prioridad, Proceso, Subproceso, TipoRegistro, Urgencia,
)


class ConfiguracionImpactoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionImpacto
        exclude = ("id",)

    GRUPOS = ("clientes", "tiempo", "financiero")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, campo in self.fields.items():
            if nombre != "predeterminada":
                campo.widget.attrs.update({"class": "input impact-range-input", "min": "0", "step": "1"})
        self.fields["predeterminada"].label = "Usar esta configuración como predeterminada"

    def clean(self):
        datos = super().clean()
        for grupo in self.GRUPOS:
            bajo_desde = datos.get(f"{grupo}_bajo_desde")
            bajo_hasta = datos.get(f"{grupo}_bajo_hasta")
            medio_desde = datos.get(f"{grupo}_medio_desde")
            medio_hasta = datos.get(f"{grupo}_medio_hasta")
            alto_desde = datos.get(f"{grupo}_alto_desde")
            if None in (bajo_desde, bajo_hasta, medio_desde, medio_hasta, alto_desde):
                continue
            if not (bajo_desde <= bajo_hasta < medio_desde <= medio_hasta < alto_desde):
                raise forms.ValidationError("Los rangos de cada criterio deben estar ordenados y no pueden superponerse.")
            if medio_desde != bajo_hasta + 1 or alto_desde != medio_hasta + 1:
                raise forms.ValidationError("Los rangos deben ser continuos: cada nivel comienza inmediatamente después del anterior.")
        return datos

class ConfiguracionUrgenciaForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionUrgencia
        fields = ("activo", "bajo_desde", "bajo_hasta", "medio_desde", "medio_hasta", "alto_desde")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nombre, campo in self.fields.items():
            if nombre != "activo":
                campo.widget.attrs.update({"class": "input impact-range-input", "min": "0", "step": "1"})

    def clean(self):
        datos = super().clean()
        valores = [datos.get(nombre) for nombre in ("bajo_desde", "bajo_hasta", "medio_desde", "medio_hasta", "alto_desde")]
        if None not in valores:
            bajo_desde, bajo_hasta, medio_desde, medio_hasta, alto_desde = valores
            if not (bajo_desde <= bajo_hasta < medio_desde <= medio_hasta < alto_desde):
                raise forms.ValidationError("Los rangos deben estar ordenados y no pueden superponerse.")
            if medio_desde != bajo_hasta + 1 or alto_desde != medio_hasta + 1:
                raise forms.ValidationError("Los rangos deben ser continuos: cada nivel comienza inmediatamente después del anterior.")
        return datos


# Lista explícita: nunca aceptar un nombre de modelo enviado por el navegador.
CATALOGOS = {
    "tipos": (TipoRegistro, ["nombre", "activo"], "Tipos de registro"),
    "fuentes": (FuenteDeteccion, ["codigo", "nombre", "activo"], "Fuentes de detección"),
    "procesos": (Proceso, ["nombre", "gerencia", "responsable", "validadores", "activo"], "Procesos"),
    "subprocesos": (Subproceso, ["proceso", "nombre", "activo"], "Subprocesos"),
    "impactos": (Impacto, ["nombre", "activo"], "Niveles de impacto"),
    "urgencias": (Urgencia, ["nombre", "activo"], "Urgencias"),
    "prioridades": (Prioridad, ["codigo", "nombre", "activo"], "Prioridades"),
    "matriz": (MatrizPrioridad, ["impacto", "urgencia", "prioridad", "activo", "es_demo"], "Matriz de prioridad"),
    "categorias": (CategoriaCausa, ["nombre", "orden", "activo"], "Categorías 6M"),
    "preguntas": (PreguntaCausa, ["codigo", "categoria", "texto", "orden", "activo"], "Preguntas 6M"),
}


def formulario_catalogo(tipo, *args, instance=None, **kwargs):
    modelo, campos, _ = CATALOGOS[tipo]
    campos_modelo = [campo for campo in campos if campo != "validadores"]
    form_class = forms.modelform_factory(modelo, fields=campos_modelo)
    form = form_class(*args, instance=instance, **kwargs)
    if "validadores" in campos:
        from apps.accounts.models import Usuario
        validadores_ids = UsuarioRol.objects.filter(
            rol="VALIDADOR",
        ).values("usuario_id")
        form.fields["validadores"] = forms.ModelMultipleChoiceField(
            queryset=Usuario.objects.filter(
                is_active=True,
                pk__in=validadores_ids,
            ),
            required=False,
            widget=forms.SelectMultiple(attrs={"class": "input"}),
            initial=instance.validadores.all() if instance and instance.pk else None,
            help_text="Selecciona los validadores autorizados. Usa Ctrl o Cmd para seleccionar varios.",
        )
    # Identificadores históricos no se renombran.
    if instance and instance.pk:
        for nombre in ("codigo", "impacto", "urgencia"):
            if nombre in form.fields:
                form.fields[nombre].disabled = True
    for nombre, campo in form.fields.items():
        campo.widget.attrs.setdefault("class", "input")
        if nombre in ("responsable", "responsable_ti"):
            campo.queryset = campo.queryset.filter(is_active=True)
    return form
