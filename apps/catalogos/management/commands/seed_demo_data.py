"""Datos demostrativos separados de la semilla de maestros."""
import getpass
import os
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import Usuario
from apps.catalogos.models import FuenteDeteccion, Proceso, TipoRegistro, Urgencia
from apps.hallazgos.models import Hallazgo
from apps.hallazgos.services import HallazgoService


class Command(BaseCommand):
    help = "Crea ejemplos locales. Solicita contraseña sin mostrarla; --noinput no inventa credenciales."

    def add_arguments(self, parser):
        parser.add_argument("--noinput", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG or not settings.ENABLE_DEMO_DATA:
            raise CommandError("Demo deshabilitada. Solo habilitar DEBUG y ENABLE_DEMO_DATA en desarrollo.")
        call_command("seed_initial_data", stdout=self.stdout)
        password = os.environ.get("DEMO_PASSWORD")
        if not options["noinput"] and not password:
            password = getpass.getpass("Contraseña local para las tres cuentas demo (mínimo 12 caracteres): ")
            if password != getpass.getpass("Repite la contraseña: "):
                raise CommandError("Las contraseñas no coinciden.")
        if password:
            validate_password(password)
        usuarios = {}
        for nombre, rol, nombres, apellidos in [
            ("admin.demo", "ADMINISTRADOR", "Administración", "Demo"),
            ("usuario.demo", "USUARIO", "Juan", "Pérez"),
            ("validador.demo", "VALIDADOR", "Calidad", "Demo"),
        ]:
            obj, creado = Usuario.objects.get_or_create(username=nombre, defaults={"first_name": nombres, "last_name": apellidos, "area": "Demostración"})
            if password:
                obj.set_password(password)
                obj.save(update_fields=["password"])
            elif creado:
                obj.set_unusable_password()
                obj.save(update_fields=["password"])
            obj.groups.add(Group.objects.get(name=rol))
            usuarios[rol] = obj
        proceso, _ = Proceso.objects.get_or_create(nombre="Operación telecom · DEMO", defaults={"responsable": usuarios["USUARIO"]})
        proceso.validadores.add(usuarios["VALIDADOR"])
        for titulo, tipo in [("Intermitencia en servicio", "INC"), ("Incidencia en facturación", "INC"), ("Error de provisión", "PBI")]:
            if not Hallazgo.objects.filter(titulo=titulo, registrado_por=usuarios["USUARIO"], proceso=proceso).exists():
                HallazgoService.crear(usuario=usuarios["USUARIO"], datos={
                    "titulo": titulo, "tipo_registro": TipoRegistro.objects.get(codigo=tipo),
                    "fuente_deteccion": FuenteDeteccion.objects.get(codigo="OPERACION"),
                    "proceso": proceso, "responsable": usuarios["USUARIO"],
                    "descripcion": f"DEMO: {titulo}. Ejemplo migrado del HTML; no corresponde a un incidente real.",
                    "fecha_deteccion": timezone.now(), "fecha_solucion": timezone.localdate() + timedelta(days=7),
                    "impacto_clientes": 1, "impacto_tiempo": 2, "impacto_soles": 1,
                    "urgencia": Urgencia.objects.get(valor=2), "es_critica": "NO",
                    "criterio_categoria": "DEMO: clasificación manual para revisar el recorrido.",
                    "requisito_referencia": "DEMO: compromiso de continuidad del servicio.",
                })
        self.stdout.write(self.style.SUCCESS("Tres cuentas y casos DEMO disponibles. No se sobrescribieron casos existentes."))
        if not password:
            self.stdout.write("Las cuentas nuevas no tienen contraseña utilizable. Ejecuta seed_demo_data sin --noinput o changepassword antes de iniciar sesión.")
