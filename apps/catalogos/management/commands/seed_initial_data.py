"""Semilla idempotente: maestros, roles y preguntas exactas del HTML."""
import json
from pathlib import Path
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction
from apps.catalogos.models import (
    CategoriaCausa, FuenteDeteccion, Impacto, MatrizPrioridad,
    PreguntaCausa, Prioridad, TipoRegistro, Urgencia,
)

ROLES = {
    "USUARIO": ["registrar_hallazgo"],
    "VALIDADOR": ["validar_hallazgo", "gestionar_tratamiento", "evaluar_eficacia", "cerrar_hallazgo"],
    "ADMINISTRADOR": ["administrar_plataforma", "ver_todos_hallazgos"],
}
FUENTES = [
    ("OPERACION", "Operación / Proceso"), ("FALLA_CRITICA", "Falla crítica"),
    ("AUDITORIA", "Hallazgo de auditoría"), ("OKR", "Incumplimiento periódico de OKR"),
    ("QUEJA", "Queja / Reclamo"), ("RIESGOS", "Riesgos y oportunidades"),
    ("REVISION", "Revisión de procesos"), ("LEGAL", "Legal / Regulatorio / Contractual"), ("OTRO", "Otro"),
]


class Command(BaseCommand):
    help = "Crea maestros y permisos sin sobrescribir configuraciones existentes."

    @transaction.atomic
    def handle(self, *args, **options):
        for nombre, codenames in ROLES.items():
            grupo, _ = Group.objects.get_or_create(name=nombre)
            permisos = Permission.objects.filter(content_type__app_label="accounts", codename__in=codenames)
            if permisos.count() != len(codenames):
                raise RuntimeError("Ejecuta migrate antes de la semilla.")
            grupo.permissions.add(*permisos)
        for codigo, nombre in [("INC", "Incidente"), ("PBI", "Problema (PBI)"), ("SNC", "Salida No Conforme"), ("NOC", "No Conforme")]:
            TipoRegistro.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre})
        for codigo, nombre in FUENTES:
            FuenteDeteccion.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre})
        for valor, nombre in enumerate(["Bajo", "Medio", "Alto"], 1):
            Impacto.objects.get_or_create(valor=valor, defaults={"nombre": nombre})
        for valor, nombre in enumerate(["Baja", "Media", "Alta"], 1):
            Urgencia.objects.get_or_create(valor=valor, defaults={"nombre": nombre})
        for codigo, nombre in [("BAJA", "Baja"), ("MEDIA", "Media"), ("ALTA", "Alta"), ("CRITICA", "Crítica")]:
            Prioridad.objects.get_or_create(codigo=codigo, defaults={"nombre": nombre})
        # TODO negocio: reemplazar esta matriz DEMO por la oficial aprobada.
        demo = [["BAJA", "MEDIA", "ALTA"], ["MEDIA", "ALTA", "ALTA"], ["ALTA", "ALTA", "CRITICA"]]
        for impacto, fila in enumerate(demo, 1):
            for urgencia, prioridad in enumerate(fila, 1):
                MatrizPrioridad.objects.get_or_create(impacto=Impacto.objects.get(valor=impacto), urgencia=Urgencia.objects.get(valor=urgencia), defaults={"prioridad": Prioridad.objects.get(codigo=prioridad), "es_demo": True})
        ruta = Path(__file__).resolve().parents[2] / "data" / "preguntas_6m.json"
        for categoria in json.loads(ruta.read_text()):
            obj, _ = CategoriaCausa.objects.get_or_create(codigo=categoria["codigo"], defaults={"nombre": categoria["nombre"], "orden": int(categoria["codigo"])})
            for orden, pregunta in enumerate(categoria["preguntas"], 1):
                PreguntaCausa.objects.get_or_create(codigo=pregunta["codigo"], defaults={"categoria": obj, "texto": pregunta["texto"], "orden": orden})
        self.stdout.write(self.style.SUCCESS("Maestros, 3 roles y 32 preguntas 6M disponibles. Matriz de prioridad inicial: DEMO."))
