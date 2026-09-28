"""Entrada y mensajes en español. Las reglas se repiten en servicios para POST directo."""
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.catalogos.models import ConfiguracionImpacto, MatrizPrioridad, PreguntaCausa, Proceso, TipoRegistro
from .estados import ESTADOS
from .models import Accion, CicloTratamiento, ComunicacionHallazgo, EvaluacionEficacia, Hallazgo, PBI, SI_NO_NA
from .services.evidencia import validar_archivo
from .services.hallazgo import CAMPOS_HALLAZGO

FECHA = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
FECHA_HORA = forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")


class EstiloForm:
    def estilizar(self):
        for nombre, campo in self.fields.items():
            if not isinstance(campo.widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
                campo.widget.attrs.setdefault("class", "input")
            if isinstance(campo.widget, forms.Textarea):
                campo.widget.attrs.setdefault("rows", 3)


class HallazgoForm(EstiloForm, forms.ModelForm):
    CAMPOS_VISIBLES = [
        "tipo_registro", "fuente_deteccion", "proceso", "subproceso", "actividad",
        "descripcion", "origen_tecnologico", "ticket_remedy", "responsable", "fecha_deteccion", "fecha_solucion",
        "impacto_clientes", "impacto_tiempo", "impacto_soles", "urgencia", "es_critica",
    ]

    class Meta:
        model = Hallazgo
        fields = CAMPOS_HALLAZGO
        widgets = {"fecha_deteccion": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), "fecha_solucion": FECHA,
            "descripcion": forms.Textarea(attrs={"rows": 4}), "criterio_categoria": forms.Textarea(attrs={"rows": 2}),
            "requisito_referencia": forms.Textarea(attrs={"rows": 2}), "justificacion_no_impacto": forms.Textarea(attrs={"rows": 2})}
        labels = {"tipo_registro": "Tipo de registro", "fuente_deteccion": "Fuente de detección", "es_critica": "¿No conformidad crítica?", "criterio_categoria": "Criterio de categorización", "requisito_referencia": "Requisito o referencia incumplida", "aplica_impacto": "Aplica evaluación de impacto", "ticket_remedy": "N.º ticket Remedy (si aplica)"}

    def __init__(self, data=None, instance=None, usuario=None, **kwargs):
        self.usuario = usuario
        super().__init__(data=data, instance=instance, **kwargs)
        for nombre in list(self.fields):
            if nombre not in self.CAMPOS_VISIBLES:
                del self.fields[nombre]
        for nombre in ("tipo_registro", "fuente_deteccion", "proceso", "subproceso", "urgencia"):
            self.fields[nombre].queryset = self.fields[nombre].queryset.filter(activo=True)
        self.fields["ticket_remedy"].widget.attrs["placeholder"] = "Ej. REM-589632"
        self.fields["actividad"].required = False
        self.fields["actividad"].label = "Actividad (opcional)"
        self.fields["actividad"].widget.attrs["placeholder"] = "Ej. Conciliación, validación o tarea relacionada"
        self.fields["descripcion"].widget.attrs["placeholder"] = "Describe de forma clara y concisa la no conformidad encontrada..."
        for nombre in ("tipo_registro", "fuente_deteccion", "urgencia"):
            self.fields[nombre].empty_label = "Seleccionar"
        self.fields["es_critica"].choices = [
            ("", "Seleccionar"),
            ("SI", "Sí - Crítica"),
            ("NO", "No - No crítica"),
        ]
        self.fields["origen_tecnologico"] = forms.TypedChoiceField(
            label="¿Es hallazgo tecnológico?",
            choices=[(True, "Sí"), (False, "No")],
            coerce=lambda valor: valor in (True, "True", "true", "1"),
            empty_value=False,
            initial=instance.origen_tecnologico if instance and instance.pk else False,
            required=False,
            widget=forms.RadioSelect,
        )
        if not self.is_bound and not (instance and instance.pk):
            procesos = list(self.fields["proceso"].queryset[:2])
            if len(procesos) == 1:
                self.initial["proceso"] = procesos[0].pk
        self.fields["responsable"].queryset = get_user_model().objects.filter(is_active=True).order_by("first_name", "username")
        for nombre in ("impacto_clientes", "impacto_tiempo", "impacto_soles"):
            self.fields[nombre] = forms.TypedChoiceField(
                label=nombre.replace("impacto_", "").capitalize(),
                choices=[(1, "Bajo"), (2, "Medio"), (3, "Alto")],
                coerce=int, empty_value=None, required=False, widget=forms.RadioSelect,
            )
        self.fields["fecha_solucion"].widget.attrs["min"] = timezone.localdate().isoformat()
        self.fields["tipo_registro"].help_text = "El tipo define el prefijo del código SAC automático."
        self.fields["es_critica"].help_text = "Antes de continuar debe definir Sí o No."
        puede_corregir = instance and instance.pk and (
            instance.estado == "EN_ANALISIS"
            or (
                instance.estado == "ACCION_INMEDIATA"
                and instance.ciclo_actual is not None
                and not instance.ciclo_actual.acciones.exists()
            )
        )
        if instance and instance.pk and not puede_corregir:
            self.fields["tipo_registro"].disabled = True
        elif usuario:
            self.fields["responsable"].initial = usuario.pk
            self.fields["fecha_deteccion"].initial = timezone.localtime().replace(second=0, microsecond=0)
        self.estilizar()

    def clean(self):
        datos = super().clean()
        if not datos.get("titulo"):
            datos["titulo"] = (datos.get("descripcion", "").strip() or "Hallazgo por completar")[:250]
        # Mostrar fecha sin hora no debe borrar la hora histórica de una edición.
        deteccion = datos.get("fecha_deteccion")
        previa = self.instance.fecha_deteccion if self.instance.pk else None
        if deteccion and previa and timezone.localdate(deteccion) == timezone.localdate(previa):
            datos["fecha_deteccion"] = previa
        fecha = datos.get("fecha_solucion")
        if fecha and fecha < timezone.localdate() and (not self.instance.pk or fecha != self.instance.fecha_solucion):
            self.add_error("fecha_solucion", "La fecha de solución no puede ser anterior a la fecha actual.")
        sub, proceso = datos.get("subproceso"), datos.get("proceso")
        if sub and proceso and sub.proceso_id != proceso.pk:
            self.add_error("subproceso", "El subproceso debe pertenecer al proceso seleccionado.")
        if datos.get("origen_tecnologico") and not datos.get("ticket_remedy", "").strip():
            self.add_error("ticket_remedy", "Este campo es obligatorio para hallazgos tecnológicos.")
        if not datos.get("aplica_impacto", True):
            if datos.get("origen_tecnologico"):
                self.add_error("aplica_impacto", "El impacto es obligatorio para un origen tecnológico.")
            if not datos.get("justificacion_no_impacto", "").strip():
                self.add_error("justificacion_no_impacto", "Justifique por qué no aplica el impacto.")
        return datos

    @property
    def datos(self):
        return self.cleaned_data

    @property
    def campos_impacto(self):
        return [self[n] for n in ("impacto_clientes", "impacto_tiempo", "impacto_soles")]

    @property
    def impacto_errores(self):
        return self.is_bound and any(campo.errors for campo in self.campos_impacto)

    @property
    def impacto_resumen(self):
        if self.instance.pk:
            if not self.instance.aplica_impacto:
                return "No aplica"
            return {1: "Bajo", 2: "Medio", 3: "Alto"}.get(self.instance.impacto_resultante, "Sin evaluar")
        return "Sin evaluar"

    @property
    def matriz_prioridad(self):
        return {
            f"{fila.impacto.valor}-{fila.urgencia_id}": fila.prioridad.nombre
            for fila in MatrizPrioridad.objects.select_related("impacto", "prioridad").filter(
                activo=True, prioridad__activo=True
            )
        }

    @property
    def configuracion_impacto(self):
        return ConfiguracionImpacto.objects.filter(pk=1).first() or ConfiguracionImpacto()

    @property
    def campos_proceso(self):
        return [self[n] for n in ("proceso", "subproceso", "actividad")]

    @property
    def puede_continuar(self):
        if not self.instance.pk or self.instance.estado in {"BORRADOR", "DEVUELTO", "EN_ANALISIS"}:
            return True
        ciclo = self.instance.ciclo_actual
        return self.instance.estado == "ACCION_INMEDIATA" and ciclo is not None and not ciclo.acciones.exists()


class TransicionForm(EstiloForm, forms.Form):
    comentario = forms.CharField(label="Motivo / observación", required=False, widget=forms.Textarea)
    version = forms.IntegerField(required=False, widget=forms.HiddenInput)
    confirmar = forms.BooleanField(label="Confirmo la operación y los datos registrados.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.estilizar()


class AnalisisCausaForm(EstiloForm, forms.Form):
    causa_raiz = forms.CharField(required=False, widget=forms.HiddenInput)
    control_tipos = forms.MultipleChoiceField(
        label="Tipo de control",
        required=False,
        choices=[("PREVENTIVO", "Preventivo"), ("DETECTIVO", "Detectivo"), ("CORRECTIVO", "Correctivo")],
        widget=forms.CheckboxSelectMultiple,
    )
    control_nombre = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Escribe el nombre del control"}))
    control_descripcion = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Describe el control"}))
    control_mitiga_riesgo = forms.ChoiceField(required=False, choices=SI_NO_NA, widget=forms.RadioSelect)
    control_frecuencia = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Ej. diaria, semanal, mensual"}))
    control_responsable = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Responsable del control"}))
    control_evidencia = forms.CharField(required=False, widget=forms.TextInput(attrs={"placeholder": "Evidencia / enlace / referencia"}))

    def __init__(self, data=None, instance=None, **kwargs):
        super().__init__(data=data, **kwargs)
        self.instance = instance
        existentes = {str(r["pregunta_id"]): r for r in instance.respuestas} if instance and instance.pk else {}
        snapshot = {str(p["id"]): p for p in instance.checklist_snapshot} if instance and instance.checklist_snapshot else {}
        consulta = PreguntaCausa.objects.select_related("categoria")
        self.preguntas = list(consulta.filter(pk__in=snapshot) if snapshot else consulta.filter(activo=True, categoria__activo=True))
        self.preguntas_fijas = []
        self.preguntas_otro = []
        self.categorias = []
        grupos = {}
        for pregunta in self.preguntas:
            nombre = pregunta.codigo.replace(".", "_")
            version = snapshot.get(str(pregunta.pk), {"codigo": pregunta.codigo, "texto": pregunta.texto})
            grupo = grupos.setdefault(pregunta.categoria_id, {"categoria": pregunta.categoria, "preguntas": [], "otro": None})
            es_otro = version.get("es_otro", version["texto"].strip().rstrip(":").casefold() == "otro")
            if es_otro:
                self.preguntas_otro.append(pregunta)
                self.fields[f"a_{nombre}"] = forms.BooleanField(required=False, widget=forms.HiddenInput)
                self.fields[f"t_{nombre}"] = forms.CharField(
                    label=f"Pregunta adicional {version['codigo']}", required=False, max_length=500,
                    widget=forms.TextInput(attrs={"placeholder": "Escribe el punto o pregunta adicional..."}),
                )
                self.fields[f"r_{nombre}"] = forms.ChoiceField(
                    label=f"Respuesta {version['codigo']}", choices=SI_NO_NA, required=False, widget=forms.RadioSelect,
                )
                self.fields[f"c_{nombre}"] = forms.CharField(
                    label=f"Comentario {version['codigo']}", required=False,
                    widget=forms.TextInput(attrs={"placeholder": "Escribe un comentario..."}),
                )
                previa = existentes.get(str(pregunta.pk))
                if previa:
                    self.initial[f"a_{nombre}"] = True
                    self.initial[f"t_{nombre}"] = previa.get("texto_snapshot", "")
                    self.initial[f"r_{nombre}"] = previa["respuesta"]
                    self.initial[f"c_{nombre}"] = previa["comentario"]
                grupo["otro"] = {
                    "pregunta": pregunta, "activo": self[f"a_{nombre}"], "texto": self[f"t_{nombre}"],
                    "respuesta": self[f"r_{nombre}"], "comentario": self[f"c_{nombre}"],
                }
                continue
            self.preguntas_fijas.append(pregunta)
            self.fields[f"r_{nombre}"] = forms.ChoiceField(
                label=f"{version['codigo']}. {version['texto']}",
                choices=SI_NO_NA,
                required=False,
                widget=forms.RadioSelect,
            )
            self.fields[f"c_{nombre}"] = forms.CharField(
                label=f"Comentario {version['codigo']}",
                required=False,
                widget=forms.TextInput(attrs={"placeholder": "Escribe un comentario..."}),
            )
            previa = existentes.get(str(pregunta.pk))
            if previa:
                self.initial[f"r_{nombre}"] = previa["respuesta"]
                self.initial[f"c_{nombre}"] = previa["comentario"]
            grupo["preguntas"].append({"pregunta": pregunta, "texto": version["texto"], "respuesta": self[f"r_{nombre}"], "comentario": self[f"c_{nombre}"]})
        self.categorias = list(grupos.values())
        if instance:
            self.initial["causa_raiz"] = instance.causa_raiz
            for nombre, valor in instance.control.items():
                self.initial[f"control_{nombre}"] = valor
        self.estilizar()

    def clean(self):
        datos = super().clean()
        for pregunta in self.preguntas_otro:
            nombre = pregunta.codigo.replace(".", "_")
            if not datos.get(f"a_{nombre}"):
                continue
            if not datos.get(f"t_{nombre}", "").strip():
                self.add_error(f"t_{nombre}", "Escribe el punto o pregunta adicional.")
            if not datos.get(f"r_{nombre}"):
                self.add_error(f"r_{nombre}", "Selecciona Sí, No o NA.")
        return datos

    def datos_servicio(self):
        respuestas = []
        for pregunta in self.preguntas_fijas:
            nombre = pregunta.codigo.replace(".", "_")
            valor = self.cleaned_data.get(f"r_{nombre}")
            if valor:
                respuestas.append({"pregunta": pregunta, "respuesta": valor, "comentario": self.cleaned_data.get(f"c_{nombre}", "")})
        otros_activos = []
        for pregunta in self.preguntas_otro:
            nombre = pregunta.codigo.replace(".", "_")
            if not self.cleaned_data.get(f"a_{nombre}"):
                continue
            otros_activos.append(str(pregunta.pk))
            respuestas.append({
                "pregunta": pregunta,
                "texto_personalizado": self.cleaned_data[f"t_{nombre}"].strip(),
                "respuesta": self.cleaned_data[f"r_{nombre}"],
                "comentario": self.cleaned_data.get(f"c_{nombre}", ""),
            })
        return {"causa_raiz": self.cleaned_data["causa_raiz"], "respuestas": respuestas,
            "otros_activos": otros_activos,
            "control": {nombre: self.cleaned_data[f"control_{nombre}"] for nombre in ("tipos", "nombre", "descripcion", "mitiga_riesgo", "frecuencia", "responsable", "evidencia")}}


class AccionForm(EstiloForm, forms.ModelForm):
    class Meta:
        model = Accion
        fields = ["tipo", "descripcion", "responsable", "fecha_inicio", "fet_inicial", "resultado_esperado", "comentario"]
        widgets = {"fecha_inicio": FECHA, "fet_inicial": FECHA}
        labels = {"fet_inicial": "Fecha estimada de término inicial"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsable"].queryset = get_user_model().objects.filter(is_active=True)
        self.fields["fecha_inicio"].initial = timezone.localdate()
        self.estilizar()

    def clean(self):
        datos = super().clean()
        inicio, fin = datos.get("fecha_inicio"), datos.get("fet_inicial")
        if fin and (fin < timezone.localdate() or (inicio and fin < inicio)):
            self.add_error("fet_inicial", "El compromiso no puede ser anterior a hoy ni al inicio.")
        return datos


class ActividadPlanForm(EstiloForm, forms.Form):
    tipo = forms.ChoiceField(choices=Accion.TIPOS)
    descripcion = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Describe la actividad"}))
    responsable = forms.ModelChoiceField(queryset=get_user_model().objects.none(), required=False, empty_label="Responsable AC")
    fet_inicial = forms.DateField(label="FET inicial", required=False, widget=FECHA)
    estado = forms.ChoiceField(choices=Accion.ESTADOS)

    def __init__(self, *args, es_critica=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsable"].queryset = get_user_model().objects.filter(is_active=True).order_by("first_name", "last_name", "username")
        if not es_critica:
            self.fields["tipo"].choices = Accion.TIPOS[:2]
        self.fields["fet_inicial"].widget.attrs["min"] = timezone.localdate().isoformat()
        self.estilizar()

    def clean_fet_inicial(self):
        valor = self.cleaned_data.get("fet_inicial")
        if valor and valor < timezone.localdate():
            raise ValidationError("La FET no puede ser anterior a hoy.")
        return valor

    def datos_servicio(self):
        descripcion = self.cleaned_data["descripcion"].strip()
        return {
            "tipo": self.cleaned_data["tipo"],
            "descripcion": descripcion,
            "responsable": self.cleaned_data.get("responsable"),
            "fecha_inicio": timezone.localdate(),
            "fet_inicial": self.cleaned_data.get("fet_inicial"),
            "estado": self.cleaned_data["estado"],
            "resultado_esperado": descripcion,
            "comentario": "",
        }


class SeguimientoLineaForm(forms.Form):
    estado = forms.ChoiceField(choices=Accion.ESTADOS)
    fecha_real = forms.DateField(required=False, widget=FECHA)

    def __init__(self, *args, accion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.accion = accion
        self.fields["fecha_real"].widget.attrs["max"] = timezone.localdate().isoformat()

    def clean(self):
        datos = super().clean()
        estado, fecha = datos.get("estado"), datos.get("fecha_real")
        if estado == "COMPLETADA" and fecha is None:
            self.add_error("fecha_real", "Indique la fecha real para completar la actividad.")
        if estado != "COMPLETADA" and fecha is not None:
            self.add_error("fecha_real", "La fecha real solo corresponde a una actividad completada.")
        if fecha and (fecha < self.accion.fecha_inicio or fecha > timezone.localdate()):
            self.add_error("fecha_real", "La fecha real debe estar entre el inicio de la actividad y hoy.")
        return datos


class SeguimientoForm(EstiloForm, forms.Form):
    estado = forms.ChoiceField(choices=Accion.ESTADOS)
    porcentaje_avance = forms.IntegerField(label="Porcentaje de avance", min_value=0, max_value=100)
    fecha_real = forms.DateField(label="Fecha real de finalización", required=False, widget=FECHA)
    comentario = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.estilizar()


class ReprogramacionForm(EstiloForm, forms.Form):
    nueva_fecha = forms.DateField(label="Nueva fecha compromiso", widget=FECHA)
    motivo = forms.CharField(widget=forms.Textarea)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nueva_fecha"].widget.attrs["min"] = timezone.localdate().isoformat()
        self.estilizar()

    def clean_nueva_fecha(self):
        valor = self.cleaned_data["nueva_fecha"]
        if valor < timezone.localdate():
            raise ValidationError("La nueva fecha no puede ser anterior a hoy.")
        return valor


class EvaluacionEficaciaForm(EstiloForm, forms.ModelForm):
    class Meta:
        model = EvaluacionEficacia
        fields = ["fecha_evaluacion", "resultado", "comentario"]
        widgets = {"fecha_evaluacion": FECHA}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_evaluacion"].initial = timezone.localdate()
        self.fields["resultado"].choices = [
            (valor, "Seleccionar" if valor == "" else etiqueta)
            for valor, etiqueta in self.fields["resultado"].choices
        ]
        self.fields["comentario"].widget.attrs["placeholder"] = "Registra el resultado de la evaluación..."
        self.estilizar()


class PBIForm(EstiloForm, forms.ModelForm):
    class Meta:
        model = PBI
        fields = ["numero_pbi", "ticket_incidente", "sistema", "herramienta", "responsable_ti", "estado", "fecha_cierre", "observacion"]
        widgets = {"fecha_cierre": FECHA}
        labels = {"numero_pbi": "N.º PBI (referencia manual)"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["responsable_ti"].queryset = get_user_model().objects.filter(is_active=True)
        self.estilizar()


class ComunicacionForm(EstiloForm, forms.ModelForm):
    class Meta:
        model = ComunicacionHallazgo
        fields = ["destinatarios", "medio", "descripcion", "fecha"]
        widgets = {"fecha": FECHA_HORA}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.estilizar()


class EvidenciaForm(EstiloForm, forms.Form):
    archivo = forms.FileField(help_text="PDF, PNG o JPEG; máximo 10 MB.")
    descripcion = forms.CharField(label="Descripción", required=False, widget=forms.Textarea)

    def __init__(self, *args, hallazgo=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.contextos = {}
        opciones = [("", "Identificación / expediente general")]
        ciclo = hallazgo.ciclo_actual if hallazgo else None
        if ciclo:
            for nombre, consulta in [("accion", ciclo.acciones.all()), ("analisis", CicloTratamiento.objects.filter(pk=ciclo.pk, analisis_inicio__isnull=False)), ("evaluacion", ciclo.evaluaciones.all())]:
                for obj in consulta:
                    clave = f"{nombre}:{obj.pk}"
                    self.contextos[clave] = (nombre, obj)
                    opciones.append((clave, f"{nombre.capitalize()} · {getattr(obj, 'codigo', obj.pk)}"))
        self.fields["contexto"] = forms.ChoiceField(label="Relacionar evidencia con", choices=opciones, required=False)
        self.estilizar()

    def clean(self):
        datos = super().clean()
        clave = datos.pop("contexto", "")
        if clave in self.contextos:
            nombre, obj = self.contextos[clave]
            datos[nombre] = obj
        return datos

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        validar_archivo(archivo)
        return archivo


class BuscarHallazgoForm(EstiloForm, forms.Form):
    codigo = forms.CharField(label="Código o título", required=False)
    estado = forms.ChoiceField(choices=[("", "Todos")] + ESTADOS, required=False)
    tipo_registro = forms.ModelChoiceField(label="Tipo", queryset=TipoRegistro.objects.all(), required=False)
    proceso = forms.ModelChoiceField(queryset=Proceso.objects.all(), required=False)
    fecha_desde = forms.DateField(required=False, widget=FECHA)
    fecha_hasta = forms.DateField(required=False, widget=FECHA)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.estilizar()

    def clean(self):
        datos = super().clean()
        desde, hasta = datos.get("fecha_desde"), datos.get("fecha_hasta")
        if desde and hasta and desde > hasta:
            self.add_error("fecha_hasta", "La fecha final debe ser igual o posterior a la inicial.")
        return datos
