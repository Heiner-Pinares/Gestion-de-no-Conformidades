from django import forms
from .models import (
    CategoriaCausa, FuenteDeteccion, Impacto, MatrizPrioridad, PreguntaCausa,
    Prioridad, Proceso, Subproceso, TipoRegistro, Urgencia,
)

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
    form_class = forms.modelform_factory(modelo, fields=campos)
    form = form_class(*args, instance=instance, **kwargs)
    # Identificadores históricos no se renombran.
    if instance and instance.pk:
        for nombre in ("codigo", "impacto", "urgencia"):
            if nombre in form.fields:
                form.fields[nombre].disabled = True
    for nombre, campo in form.fields.items():
        campo.widget.attrs.setdefault("class", "input")
        if nombre == "validadores":
            campo.queryset = campo.queryset.filter(is_active=True, groups__name="VALIDADOR").distinct()
            campo.help_text = "Selecciona los validadores autorizados para este proceso. Usa Ctrl o Cmd para seleccionar varios."
        if nombre in ("responsable", "responsable_ti"):
            campo.queryset = campo.queryset.filter(is_active=True)
    return form
