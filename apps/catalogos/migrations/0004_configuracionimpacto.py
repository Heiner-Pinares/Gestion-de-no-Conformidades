from django.db import migrations, models


def crear_configuracion(apps, schema_editor):
    ConfiguracionImpacto = apps.get_model("catalogos", "ConfiguracionImpacto")
    ConfiguracionImpacto.objects.get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies = [("catalogos", "0003_retirar_catalogos_separados")]
    operations = [
        migrations.CreateModel(
            name="ConfiguracionImpacto",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("predeterminada", models.BooleanField(default=True)),
                ("clientes_bajo_desde", models.PositiveBigIntegerField(default=0)),
                ("clientes_bajo_hasta", models.PositiveBigIntegerField(default=99)),
                ("clientes_medio_desde", models.PositiveBigIntegerField(default=100)),
                ("clientes_medio_hasta", models.PositiveBigIntegerField(default=499)),
                ("clientes_alto_desde", models.PositiveBigIntegerField(default=500)),
                ("tiempo_bajo_desde", models.PositiveIntegerField(default=0)),
                ("tiempo_bajo_hasta", models.PositiveIntegerField(default=29)),
                ("tiempo_medio_desde", models.PositiveIntegerField(default=30)),
                ("tiempo_medio_hasta", models.PositiveIntegerField(default=120)),
                ("tiempo_alto_desde", models.PositiveIntegerField(default=121)),
                ("financiero_bajo_desde", models.DecimalField(decimal_places=0, default=0, max_digits=14)),
                ("financiero_bajo_hasta", models.DecimalField(decimal_places=0, default=999999, max_digits=14)),
                ("financiero_medio_desde", models.DecimalField(decimal_places=0, default=1000000, max_digits=14)),
                ("financiero_medio_hasta", models.DecimalField(decimal_places=0, default=1999999, max_digits=14)),
                ("financiero_alto_desde", models.DecimalField(decimal_places=0, default=2000000, max_digits=14)),
            ],
            options={
                "verbose_name": "configuración de impacto",
                "verbose_name_plural": "configuración de impacto",
            },
        ),
        migrations.RunPython(crear_configuracion, migrations.RunPython.noop),
    ]
