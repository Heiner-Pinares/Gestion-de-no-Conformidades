from django.db import migrations, models


def completar_snapshots(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT rg.id, COALESCE(u.area, ''), cat.valor, cat.nombre
              FROM registro_general rg
              LEFT JOIN usuario u ON u.id = rg.registrado_por_id
              LEFT JOIN configuracion cat ON cat.id = rg.urgencia_id
            """
        )
        filas = []
        for hallazgo_id, area, nivel, nombre in cursor.fetchall():
            normalizada = (area or '').lower()
            if 'post' in normalizada and ('factur' in normalizada):
                area_snapshot = 'Post facturación'
            elif 'factur' in normalizada:
                area_snapshot = 'Facturación'
            else:
                area_snapshot = area or ''
            rango = {1: 'Menos de 28 h', 2: 'De 28 a 32 h', 3: 'Más de 32 h'}.get(nivel, nombre or '')
            filas.append((rango, area_snapshot, hallazgo_id))
        cursor.executemany(
            "UPDATE registro_general SET urgencia_seleccion = %s, urgencia_area = %s WHERE id = %s",
            filas,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("catalogos", "0007_configuracionurgencia"),
        ("hallazgos", "0019_reconstruir_rangos_impacto_historicos"),
    ]
    operations = [
        migrations.AddField(
            model_name="hallazgo", name="urgencia_area",
            field=models.CharField(blank=True, editable=False, max_length=80),
        ),
        migrations.AddField(
            model_name="hallazgo", name="urgencia_seleccion",
            field=models.CharField(blank=True, editable=False, max_length=180),
        ),
        migrations.RunPython(completar_snapshots, migrations.RunPython.noop),
    ]
