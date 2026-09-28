from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("hallazgos", "0009_flujo_directo_sin_validacion")]

    operations = [
        migrations.AlterField(
            model_name="accion",
            name="responsable",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="acciones_asignadas", to="accounts.usuario"),
        ),
        migrations.AlterField(
            model_name="accion",
            name="fet_inicial",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="accion",
            name="fecha_vigente",
            field=models.DateField(blank=True, null=True),
        ),
    ]
