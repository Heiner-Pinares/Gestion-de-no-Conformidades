from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalogos.services import reparar_textos_corruptos


class Command(BaseCommand):
    help = "Corrige textos 6M con codificación dañada sin alterar textos válidos."

    @transaction.atomic
    def handle(self, *args, **options):
        resultado = reparar_textos_corruptos()
        total = sum(resultado.values())
        detalle = ", ".join(f"{nombre}: {cantidad}" for nombre, cantidad in resultado.items())
        self.stdout.write(self.style.SUCCESS(
            f"Reparación UTF-8 completada ({total} registros). {detalle}."
        ))
