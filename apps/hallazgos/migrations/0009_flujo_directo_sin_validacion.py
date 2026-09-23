from django.db import migrations
from django.utils import timezone


def avanzar_registros_pendientes(apps, schema_editor):
    Hallazgo = apps.get_model("hallazgos", "Hallazgo")
    Ciclo = apps.get_model("hallazgos", "CicloTratamiento")
    Historial = apps.get_model("hallazgos", "HistorialHallazgo")

    for hallazgo in Hallazgo.objects.filter(
        estado__in=["PENDIENTE_VALIDACION", "VALIDADO", "DEVUELTO"]
    ).iterator():
        anterior = hallazgo.estado
        actor_id = hallazgo.registrado_por_id or hallazgo.responsable_id
        if anterior == "DEVUELTO":
            destino = "BORRADOR"
        else:
            destino = "EN_ANALISIS" if hallazgo.es_critica == "SI" else "ACCION_INMEDIATA"
            if not Ciclo.objects.filter(hallazgo_id=hallazgo.pk).exists():
                Ciclo.objects.create(
                    hallazgo_id=hallazgo.pk,
                    numero=1,
                    motivo="Tratamiento inicial",
                    creado_por_id=actor_id,
                )
        hallazgo.estado = destino
        hallazgo.version += 1
        hallazgo.updated_by_id = actor_id
        hallazgo.save(update_fields=["estado", "version", "updated_by", "updated_at"])
        Historial.objects.create(
            hallazgo_id=hallazgo.pk,
            usuario_id=actor_id,
            fecha_hora=timezone.now(),
            accion="MIGRACION_FLUJO_DIRECTO",
            estado_anterior=anterior,
            estado_nuevo=destino,
            comentario="Se retiró la validación administrativa intermedia.",
            metadata_json={"migracion": "0009_flujo_directo_sin_validacion"},
        )


class Migration(migrations.Migration):
    dependencies = [("hallazgos", "0008_actividad_opcional")]
    operations = [
        migrations.RunPython(avanzar_registros_pendientes, migrations.RunPython.noop),
    ]
