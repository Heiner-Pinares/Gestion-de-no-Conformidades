from django.core.management.base import BaseCommand

from apps.catalogos.services import sincronizar_catalogo_identificacion


class Command(BaseCommand):
    help = "Reemplaza por DML las opciones de Proceso, Subproceso y Actividad de identificación."

    def handle(self, *args, **options):
        resultado = sincronizar_catalogo_identificacion()
        self.stdout.write(self.style.SUCCESS(
            "Catálogo de identificación sincronizado: "
            f"1 proceso, 3 subprocesos y {resultado['actividades']} actividades vigentes. "
            "Los valores anteriores quedaron inactivos y sus históricos se conservaron."
        ))
