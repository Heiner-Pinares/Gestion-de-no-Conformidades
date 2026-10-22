"""Recupera correos detenidos o fallidos antes de completar el envío."""

from django.core.management.base import BaseCommand, CommandError

from apps.hallazgos.models import Accion, HistorialHallazgo
from apps.hallazgos.services.correo_compromisos import (
    CorreoCompromisoError,
    CorreoCompromisoService,
)


class Command(BaseCommand):
    help = (
        "Reintenta correos de compromisos que quedaron en INICIADO o FALLIDO. "
        "Requiere confirmar que el mensaje no llegó a enviarse."
    )

    def add_arguments(self, parser):
        parser.add_argument("--hallazgo-id", type=int, required=True)
        parser.add_argument(
            "--confirmar-no-enviado",
            action="store_true",
            help="Confirma que el error ocurrió antes de abrir la conexión SSH.",
        )

    def handle(self, *args, **options):
        if not options["confirmar_no_enviado"]:
            raise CommandError(
                "Falta --confirmar-no-enviado. No se reenvía automáticamente "
                "un intento cuyo resultado podría ser incierto."
            )

        hallazgo_id = options["hallazgo_id"]
        eventos = list(
            HistorialHallazgo.objects.filter(
                hallazgo_id=hallazgo_id,
                accion__in={
                    "CORREO_COMPROMISO_INICIADO",
                    "CORREO_COMPROMISO_FALLIDO",
                },
                accion_relacionada__isnull=False,
            ).select_related("accion_relacionada", "usuario")
        )
        if not eventos:
            raise CommandError(
                f"El hallazgo {hallazgo_id} no tiene correos recuperables."
            )

        recuperados = 0
        omitidos = 0
        fallidos: list[str] = []
        acciones_vistas: set[int] = set()
        for evento in eventos:
            accion = evento.accion_relacionada
            if accion.pk in acciones_vistas:
                continue
            acciones_vistas.add(accion.pk)
            estados = set(
                HistorialHallazgo.objects.filter(accion_relacionada=accion).values_list(
                    "accion", flat=True
                )
            )
            if "CORREO_COMPROMISO_ACEPTADO" in estados:
                self.stdout.write(
                    self.style.WARNING(f"{accion.codigo}: omitido; ya fue aceptado.")
                )
                omitidos += 1
                continue
            if "CORREO_COMPROMISO_INCIERTO" in estados:
                self.stdout.write(
                    self.style.WARNING(
                        f"{accion.codigo}: omitido; el resultado anterior es incierto."
                    )
                )
                omitidos += 1
                continue

            intentos_accion = HistorialHallazgo.objects.filter(
                accion_relacionada=accion,
                accion__in={
                    "CORREO_COMPROMISO_INICIADO",
                    "CORREO_COMPROMISO_FALLIDO",
                },
            )
            usuario = intentos_accion.order_by("fecha_hora", "pk").first().usuario
            for iniciado in intentos_accion.filter(
                accion="CORREO_COMPROMISO_INICIADO"
            ):
                metadata = dict(iniciado.metadata_json or {})
                metadata["resultado"] = "RECUPERADO_ANTES_DE_SSH"
                iniciado.accion = "CORREO_COMPROMISO_FALLIDO"
                iniciado.comentario = (
                    "Intento recuperado manualmente: el fallo ocurrió antes de abrir SSH."
                )
                iniciado.metadata_json = metadata
                iniciado.save(
                    update_fields=["accion", "comentario", "metadata_json"]
                )

            try:
                resultado = CorreoCompromisoService.enviar_asignacion(
                    accion=Accion.objects.get(pk=accion.pk),
                    usuario=usuario,
                )
            except CorreoCompromisoError as error:
                fallidos.append(f"{accion.codigo}: {error}")
                self.stderr.write(self.style.ERROR(fallidos[-1]))
            else:
                if resultado.aceptado:
                    recuperados += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"{accion.codigo}: correo aceptado por sendmail.")
                    )

        self.stdout.write(
            f"Resultado: {recuperados} recuperado(s), {omitidos} omitido(s), "
            f"{len(fallidos)} fallido(s)."
        )
        if fallidos:
            raise CommandError("Uno o más correos no pudieron recuperarse.")
