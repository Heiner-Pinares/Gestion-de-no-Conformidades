from importlib import import_module

from django.db import migrations


def recrear_vista(apps, schema_editor):
    # La compactación elimina las tablas auxiliares con CASCADE; por eso se
    # recompone después la vista de negocio usando su definición versionada.
    modulo = import_module("apps.hallazgos.migrations.0005_vista_registro_general")
    sql = modulo.Migration.operations[0].sql
    schema_editor.execute("DROP VIEW IF EXISTS registro_general")
    schema_editor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [("hallazgos", "0006_maximo_diez_tablas")]
    operations = [migrations.RunPython(recrear_vista, migrations.RunPython.noop)]
