from django.db import migrations, models


def compactar_configuracion_impacto(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        raise RuntimeError("La compactación física requiere PostgreSQL.")

    schema_editor.execute(
        """
        DO $compactar$
        DECLARE
            columnas text;
        BEGIN
            IF EXISTS (
                SELECT 1
                  FROM pg_class c
                  JOIN pg_namespace n ON n.oid = c.relnamespace
                 WHERE n.nspname = 'public'
                   AND c.relname = 'catalogos_configuracionimpacto'
                   AND c.relkind = 'r'
            ) THEN
                SELECT string_agg(
                           format('%%I %%s', a.attname, pg_catalog.format_type(a.atttypid, a.atttypmod)),
                           ', ' ORDER BY a.attnum
                       )
                  INTO columnas
                  FROM pg_attribute a
                 WHERE a.attrelid = 'public.catalogos_configuracionimpacto'::regclass
                   AND a.attnum > 0 AND NOT a.attisdropped;

                DROP TYPE IF EXISTS _aux_catalogos_configuracionimpacto CASCADE;
                EXECUTE format(
                    'CREATE TYPE _aux_catalogos_configuracionimpacto AS (%%s)',
                    columnas
                );
                INSERT INTO sistema_registro_auxiliar(tipo, clave, datos)
                SELECT 'catalogos_configuracionimpacto', id::text, to_jsonb(origen)
                  FROM catalogos_configuracionimpacto origen
                ON CONFLICT (tipo, clave) DO UPDATE SET datos = EXCLUDED.datos;

                DROP TABLE catalogos_configuracionimpacto CASCADE;
                CREATE VIEW catalogos_configuracionimpacto AS
                SELECT (jsonb_populate_record(
                    NULL::_aux_catalogos_configuracionimpacto,
                    datos
                )).* FROM sistema_registro_auxiliar
                WHERE tipo = 'catalogos_configuracionimpacto';

                CREATE TRIGGER auxiliar_dml
                INSTEAD OF INSERT OR UPDATE OR DELETE
                ON catalogos_configuracionimpacto
                FOR EACH ROW EXECUTE FUNCTION sistema_registro_auxiliar_dml('id');
            END IF;
        END
        $compactar$;
        """
    )


REGISTRO_GENERAL_SQL = """
DROP VIEW IF EXISTS registro_general;
CREATE VIEW registro_general AS
SELECT concat(h.id, ':', COALESCE(c.id, 0), ':', COALESCE(a.id, 0)) AS fila_id,
       h.id AS hallazgo_id, c.id AS ciclo_id, a.id AS accion_id,
       row_number() OVER (ORDER BY h.id, c.numero NULLS FIRST, a.id NULLS FIRST) AS numero,
       p.gerencia, p.nombre AS proceso, COALESCE(sp.nombre, '') AS sub_proceso,
       COALESCE(f.nombre, '') AS fuente_deteccion, t.nombre AS tipo_hallazgo,
       h.codigo AS numero_hallazgo, h.ticket_remedy, h.descripcion AS descripcion_hallazgo,
       h.requisito_referencia,
       COALESCE(NULLIF(trim(concat_ws(' ', rp.first_name, rp.last_name)), ''), rp.username, '') AS responsable_proceso,
       h.fecha_deteccion, h.fecha_registro,
       CASE WHEN NOT h.aplica_impacto THEN 'No aplica' ELSE COALESCE(i.nombre, '') END AS impacto,
       CASE WHEN NOT h.aplica_impacto THEN 'No aplica' ELSE CASE h.impacto_clientes WHEN 1 THEN 'Bajo' WHEN 2 THEN 'Medio' WHEN 3 THEN 'Alto' ELSE '' END END AS impacto_clientes_nivel,
       CASE WHEN NOT h.aplica_impacto THEN 'No aplica' ELSE CASE h.impacto_tiempo WHEN 1 THEN 'Bajo' WHEN 2 THEN 'Medio' WHEN 3 THEN 'Alto' ELSE '' END END AS impacto_tiempo_nivel,
       CASE WHEN NOT h.aplica_impacto THEN 'No aplica' ELSE CASE h.impacto_soles WHEN 1 THEN 'Bajo' WHEN 2 THEN 'Medio' WHEN 3 THEN 'Alto' ELSE '' END END AS impacto_financiero_nivel,
       CASE WHEN NOT h.aplica_impacto THEN 'No aplica' ELSE COALESCE(u.nombre, '') END AS urgencia,
       h.prioridad_snapshot AS prioridad_criticidad,
       CASE h.es_critica WHEN 'SI' THEN 'Sí' WHEN 'NO' THEN 'No' WHEN 'NA' THEN 'No aplica' ELSE '' END AS no_conformidad_critica,
       COALESCE(c.causa_raiz, '') AS causas_raiz,
       CASE a.tipo WHEN 'INMEDIATA' THEN 'Acción inmediata' WHEN 'CORRECTIVA' THEN 'Acción correctiva' ELSE '' END AS tipo_accion,
       COALESCE(a.descripcion, '') AS descripcion_accion,
       COALESCE(NULLIF(trim(concat_ws(' ', ra.first_name, ra.last_name)), ''), ra.username, '') AS responsable,
       a.fecha_vigente AS fet,
       CASE a.estado WHEN 'PENDIENTE' THEN 'Pendiente' WHEN 'EN_PROCESO' THEN 'En proceso' WHEN 'COMPLETADA' THEN 'Completada' ELSE CASE h.estado WHEN 'BORRADOR' THEN 'Borrador' WHEN 'PENDIENTE_VALIDACION' THEN 'Pendiente de validación' WHEN 'DEVUELTO' THEN 'Devuelto' WHEN 'VALIDADO' THEN 'Validado' WHEN 'ACCION_INMEDIATA' THEN 'Acción inmediata' WHEN 'EN_ANALISIS' THEN 'En análisis' WHEN 'PBI_EN_GESTION' THEN 'PBI en gestión' WHEN 'PLAN_ACCION' THEN 'Plan de acción' WHEN 'EN_IMPLEMENTACION' THEN 'En implementación' WHEN 'EN_VERIFICACION' THEN 'En verificación' WHEN 'CERRADO' THEN 'Cerrado' WHEN 'REABIERTO' THEN 'Reabierto' WHEN 'CANCELADO' THEN 'Cancelado' ELSE h.estado END END AS estado,
       COALESCE(ev.nombres, '') AS evidencia_implementacion,
       a.porcentaje_avance, COALESCE(a.comentario, '') AS comentario,
       e.fecha_evaluacion AS fecha_evaluacion_eficacia,
       CASE e.resultado WHEN 'EFICAZ' THEN 'Eficaz' WHEN 'NO_EFICAZ' THEN 'No eficaz' ELSE '' END AS resultado_eficacia,
       c.fecha_cierre,
       COALESCE(NULLIF(trim(concat_ws(' ', verificador.first_name, verificador.last_name)), ''), verificador.username, '') AS auditor_verificador,
       concat_ws(E'\n', CASE WHEN e.comentario IS NOT NULL THEN 'Evaluación: ' || e.comentario END,
                 CASE WHEN c.comentarios_cierre <> '' THEN 'Cierre: ' || c.comentarios_cierre END) AS comentarios
FROM hallazgos_hallazgo h
JOIN catalogos_proceso p ON p.id = h.proceso_id
LEFT JOIN catalogos_subproceso sp ON sp.id = h.subproceso_id
JOIN catalogos_catalogo t ON t.id = h.tipo_registro_id
LEFT JOIN catalogos_catalogo f ON f.id = h.fuente_deteccion_id
LEFT JOIN catalogos_catalogo u ON u.id = h.urgencia_id
LEFT JOIN catalogos_catalogo i ON i.clase = 'IMPACTO' AND i.valor = h.impacto_resultante
LEFT JOIN accounts_usuario rp ON rp.id = p.responsable_id
LEFT JOIN hallazgos_ciclotratamiento c ON c.hallazgo_id = h.id
LEFT JOIN hallazgos_accion a ON a.ciclo_id = c.id
LEFT JOIN accounts_usuario ra ON ra.id = a.responsable_id
LEFT JOIN LATERAL (
    SELECT ee.* FROM hallazgos_evaluacioneficacia ee WHERE ee.ciclo_id = c.id
    ORDER BY ee.fecha_registro DESC, ee.id DESC LIMIT 1
) e ON true
LEFT JOIN LATERAL (
    SELECT hh.usuario_id FROM hallazgos_historialhallazgo hh WHERE hh.hallazgo_id = h.id AND hh.accion = 'VALIDAR'
    ORDER BY hh.fecha_hora DESC, hh.id DESC LIMIT 1
) val ON true
LEFT JOIN accounts_usuario verificador ON verificador.id = COALESCE(e.evaluador_id, c.responsable_cierre_id, val.usuario_id)
LEFT JOIN LATERAL (
    SELECT string_agg(evi.nombre_original, E'\n' ORDER BY evi.id) AS nombres
    FROM hallazgos_evidencia evi
    WHERE evi.hallazgo_id = h.id AND (evi.accion_id = a.id OR
       (a.id IS NULL AND evi.accion_id IS NULL AND evi.analisis_id IS NULL AND evi.evaluacion_id IS NULL AND evi.cierre_id IS NULL))
) ev ON true;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("catalogos", "0004_configuracionimpacto"),
        ("hallazgos", "0010_actividades_plan_flexible"),
    ]

    operations = [
        migrations.AddField(
            model_name="registrogeneral",
            name="impacto_clientes_nivel",
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name="registrogeneral",
            name="impacto_financiero_nivel",
            field=models.TextField(null=True),
        ),
        migrations.AddField(
            model_name="registrogeneral",
            name="impacto_tiempo_nivel",
            field=models.TextField(null=True),
        ),
        migrations.RunPython(compactar_configuracion_impacto, migrations.RunPython.noop),
        migrations.RunSQL(REGISTRO_GENERAL_SQL, migrations.RunSQL.noop),
    ]
