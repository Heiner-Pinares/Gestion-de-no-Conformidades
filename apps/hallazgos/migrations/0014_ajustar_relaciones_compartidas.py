from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("hallazgos", "0013_seis_tablas_fisicas")]
    operations = [migrations.RunSQL(
        """
        ALTER TABLE configuracion DROP CONSTRAINT IF EXISTS configuracion_responsable_fk;
        ALTER TABLE evento DROP CONSTRAINT IF EXISTS evento_hallazgo_fk;
        """,
        migrations.RunSQL.noop,
    )]
