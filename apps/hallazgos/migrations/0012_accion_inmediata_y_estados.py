from importlib import import_module

from django.db import migrations, models


def _sql_registro_general(actualizado):
    sql = import_module(
        "apps.hallazgos.migrations.0011_impacto_configurable_registro_general"
    ).REGISTRO_GENERAL_SQL
    if not actualizado:
        return sql
    return sql.replace(
        "CASE a.tipo WHEN 'INMEDIATA' THEN 'Acción inmediata' WHEN 'CORRECTIVA' THEN 'Acción correctiva' ELSE '' END AS tipo_accion",
        "CASE a.tipo WHEN 'INMEDIATA' THEN 'Solución inmediata' WHEN 'ACCION_INMEDIATA' THEN 'Acción inmediata' WHEN 'CORRECTIVA' THEN 'Acción correctiva' ELSE '' END AS tipo_accion",
    ).replace(
        "WHEN 'COMPLETADA' THEN 'Completada' ELSE CASE h.estado",
        "WHEN 'COMPLETADA' THEN 'Terminado' WHEN 'CANCELADA' THEN 'Cancelado' ELSE CASE h.estado",
    )


def actualizar_registro_general(apps, schema_editor):
    schema_editor.execute(_sql_registro_general(True))


def quitar_registro_general(apps, schema_editor):
    schema_editor.execute("DROP VIEW IF EXISTS registro_general;")


class Migration(migrations.Migration):
    dependencies = [("hallazgos", "0011_impacto_configurable_registro_general")]

    operations = [
        migrations.RunSQL(
            "DROP VIEW IF EXISTS registro_general;",
            _sql_registro_general(False),
        ),
        migrations.RemoveConstraint(model_name="accion", name="accion_tipo_valido"),
        migrations.RemoveConstraint(model_name="accion", name="accion_estado_valido"),
        migrations.AlterField(
            model_name="accion",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("INMEDIATA", "Solución inmediata"),
                    ("ACCION_INMEDIATA", "Acción inmediata"),
                    ("CORRECTIVA", "Acción correctiva"),
                ],
                max_length=18,
            ),
        ),
        migrations.AlterField(
            model_name="accion",
            name="estado",
            field=models.CharField(
                choices=[
                    ("PENDIENTE", "Pendiente"),
                    ("EN_PROCESO", "En proceso"),
                    ("COMPLETADA", "Terminado"),
                    ("CANCELADA", "Cancelado"),
                ],
                default="PENDIENTE",
                max_length=12,
            ),
        ),
        migrations.AddConstraint(
            model_name="accion",
            constraint=models.CheckConstraint(
                condition=models.Q(tipo__in=["INMEDIATA", "ACCION_INMEDIATA", "CORRECTIVA"]),
                name="accion_tipo_valido",
            ),
        ),
        migrations.AddConstraint(
            model_name="accion",
            constraint=models.CheckConstraint(
                condition=models.Q(estado__in=["PENDIENTE", "EN_PROCESO", "COMPLETADA", "CANCELADA"]),
                name="accion_estado_valido",
            ),
        ),
        migrations.RunPython(actualizar_registro_general, quitar_registro_general),
    ]
