"""Avisos internos bajo ejecución explícita, sin servicios de correo externos."""
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from apps.hallazgos.models import Accion, Hallazgo, Notificacion


class Command(BaseCommand):
    help = "Genera avisos internos para acciones vencidas o por vencer; idempotente por día."

    def add_arguments(self, parser):
        parser.add_argument("--dias", type=int, default=3, help="Ventana explícita en días para avisar próximos vencimientos.")

    def handle(self, *args, **options):
        dias = options["dias"]
        if not 0 <= dias <= 30:
            raise CommandError("La ventana debe estar entre 0 y 30 días.")
        hoy = timezone.localdate()
        ids = Accion.objects.filter(fecha_vigente__lte=hoy+timedelta(days=dias), ciclo__fecha_fin__isnull=True).exclude(estado="COMPLETADA").values_list("pk", "ciclo__hallazgo_id")
        creados = 0
        for accion_id, hallazgo_id in list(ids):
            with transaction.atomic():
                h = Hallazgo.objects.select_for_update().get(pk=hallazgo_id)
                a = Accion.objects.select_for_update().select_related("ciclo").get(pk=accion_id)
                if h.estado in {"CERRADO", "CANCELADO"} or a.estado == "COMPLETADA" or a.ciclo.fecha_fin or a.fecha_vigente > hoy+timedelta(days=dias):
                    continue
                tipo = f"vencimiento_{hoy.isoformat()}_{a.pk}"
                _, nuevo = Notificacion.objects.get_or_create(usuario=a.responsable, hallazgo=h, tipo=tipo, defaults={
                    "titulo": f"{a.codigo} · {'Vencida' if a.fecha_vigente < hoy else 'Próximo vencimiento'}",
                    "mensaje": f"La fecha vigente es {a.fecha_vigente:%d/%m/%Y}. Revisa el avance de la acción.",
                })
                creados += int(nuevo)
        self.stdout.write(self.style.SUCCESS(f"{creados} avisos internos creados; ventana de {dias} días. No se enviaron correos."))
