from django.db import migrations, models


def crear_configuraciones(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO configuracion
                (registro_tipo, codigo, nombre, activo,
                 tiempo_bajo_desde, tiempo_bajo_hasta,
                 tiempo_medio_desde, tiempo_medio_hasta, tiempo_alto_desde)
            SELECT 'CONFIGURACION_URGENCIA', datos.codigo, datos.nombre, TRUE,
                   0, 27, 28, 32, 33
              FROM (VALUES
                    ('FACTURACION', 'Emisión de facturación'),
                    ('POST_FACTURACION', 'Vencimiento de ciclo')) AS datos(codigo, nombre)
             WHERE NOT EXISTS (
                 SELECT 1 FROM configuracion c
                  WHERE c.registro_tipo = 'CONFIGURACION_URGENCIA'
                    AND c.codigo = datos.codigo
             )
            """
        )


def eliminar_configuraciones(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DELETE FROM configuracion WHERE registro_tipo = 'CONFIGURACION_URGENCIA'")


class Migration(migrations.Migration):
    dependencies = [("catalogos", "0006_alter_auditoriaadministracion_table_and_more")]
    operations = [
        migrations.CreateModel(
            name="ConfiguracionUrgencia",
            fields=[
                ("registro_tipo", models.CharField(editable=False, max_length=40)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("codigo", models.CharField(choices=[("FACTURACION", "Facturación"), ("POST_FACTURACION", "Post facturación")], max_length=30)),
                ("nombre", models.CharField(max_length=180)),
                ("activo", models.BooleanField(default=True)),
                ("bajo_desde", models.PositiveIntegerField(db_column="tiempo_bajo_desde", default=0)),
                ("bajo_hasta", models.PositiveIntegerField(db_column="tiempo_bajo_hasta", default=27)),
                ("medio_desde", models.PositiveIntegerField(db_column="tiempo_medio_desde", default=28)),
                ("medio_hasta", models.PositiveIntegerField(db_column="tiempo_medio_hasta", default=32)),
                ("alto_desde", models.PositiveIntegerField(db_column="tiempo_alto_desde", default=33)),
            ],
            options={"db_table": "configuracion", "ordering": ["codigo"], "managed": False, "base_manager_name": "objects", "default_manager_name": "objects"},
        ),
        migrations.RunPython(crear_configuraciones, eliminar_configuraciones),
    ]
