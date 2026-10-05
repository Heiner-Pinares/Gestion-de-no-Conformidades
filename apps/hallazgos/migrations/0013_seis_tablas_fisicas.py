from django.db import migrations


SQL = r"""
-- 1. Perfil y roles sin tablas de autenticación auxiliares.
ALTER TABLE accounts_usuario ADD COLUMN IF NOT EXISTS roles jsonb NOT NULL DEFAULT '[]'::jsonb;
UPDATE accounts_usuario u
SET roles = COALESCE((
    SELECT jsonb_agg(DISTINCT g.name ORDER BY g.name)
    FROM accounts_usuario_groups ug
    JOIN auth_group g ON g.id = ug.group_id
    WHERE ug.usuario_id = u.id
), '[]'::jsonb);

-- 2. Una tabla física para todos los catálogos y parámetros.
CREATE TABLE configuracion_nueva (
    id bigserial PRIMARY KEY,
    registro_tipo varchar(40) NOT NULL,
    clase varchar(12), codigo varchar(30), nombre varchar(180), activo boolean,
    valor smallint, orden smallint, gerencia varchar(180), responsable_id bigint,
    validadores_ids jsonb, proceso_id bigint, impacto_id bigint, urgencia_id bigint,
    prioridad_id bigint, es_demo boolean, categoria_id bigint, texto text,
    predeterminada boolean,
    clientes_bajo_desde bigint, clientes_bajo_hasta bigint,
    clientes_medio_desde bigint, clientes_medio_hasta bigint, clientes_alto_desde bigint,
    tiempo_bajo_desde integer, tiempo_bajo_hasta integer,
    tiempo_medio_desde integer, tiempo_medio_hasta integer, tiempo_alto_desde integer,
    financiero_bajo_desde numeric(14,0), financiero_bajo_hasta numeric(14,0),
    financiero_medio_desde numeric(14,0), financiero_medio_hasta numeric(14,0),
    financiero_alto_desde numeric(14,0),
    anio smallint, ambito varchar(10), ultimo_numero integer
);

INSERT INTO configuracion_nueva
(id, registro_tipo, clase, codigo, nombre, activo, valor, orden)
SELECT id, 'CATALOGO', clase, codigo, nombre, activo, valor, orden
FROM catalogos_catalogo;

INSERT INTO configuracion_nueva
(id, registro_tipo, nombre, activo, gerencia, responsable_id, validadores_ids)
SELECT 1000000 + p.id, 'PROCESO', p.nombre, p.activo, p.gerencia, p.responsable_id,
       COALESCE((SELECT jsonb_agg(v.usuario_id ORDER BY v.usuario_id)
                 FROM catalogos_proceso_validadores v WHERE v.proceso_id=p.id), '[]'::jsonb)
FROM catalogos_proceso p;

INSERT INTO configuracion_nueva
(id, registro_tipo, nombre, activo, proceso_id)
SELECT 2000000 + id, 'SUBPROCESO', nombre, activo, 1000000 + proceso_id
FROM catalogos_subproceso;

INSERT INTO configuracion_nueva
(id, registro_tipo, activo, es_demo, impacto_id, urgencia_id, prioridad_id)
SELECT 3000000 + id, 'MATRIZ_PRIORIDAD', activo, es_demo, impacto_id, urgencia_id, prioridad_id
FROM catalogos_matrizprioridad;

INSERT INTO configuracion_nueva
(id, registro_tipo, codigo, categoria_id, texto, orden, activo)
SELECT 4000000 + row_number() OVER (ORDER BY codigo), 'PREGUNTA_CAUSA', codigo, categoria_id, texto, orden, activo
FROM catalogos_preguntacausa;

INSERT INTO configuracion_nueva (
 id, registro_tipo, predeterminada,
 clientes_bajo_desde, clientes_bajo_hasta, clientes_medio_desde, clientes_medio_hasta, clientes_alto_desde,
 tiempo_bajo_desde, tiempo_bajo_hasta, tiempo_medio_desde, tiempo_medio_hasta, tiempo_alto_desde,
 financiero_bajo_desde, financiero_bajo_hasta, financiero_medio_desde, financiero_medio_hasta, financiero_alto_desde)
SELECT 5000000 + id, 'CONFIGURACION_IMPACTO', predeterminada,
 clientes_bajo_desde, clientes_bajo_hasta, clientes_medio_desde, clientes_medio_hasta, clientes_alto_desde,
 tiempo_bajo_desde, tiempo_bajo_hasta, tiempo_medio_desde, tiempo_medio_hasta, tiempo_alto_desde,
 financiero_bajo_desde, financiero_bajo_hasta, financiero_medio_desde, financiero_medio_hasta, financiero_alto_desde
FROM catalogos_configuracionimpacto;

INSERT INTO configuracion_nueva
(id, registro_tipo, anio, ambito, ultimo_numero)
SELECT 6000000 + id, 'CORRELATIVO_SAC', anio, ambito, ultimo_numero
FROM hallazgos_correlativosac;

-- 3. Una tabla física tipada para ciclos, evaluaciones, archivos, historial y avisos.
CREATE TABLE evento_nuevo (
    id bigserial PRIMARY KEY,
    registro_tipo varchar(40) NOT NULL,
    hallazgo_id bigint, ciclo_id bigint, accion_relacionada_id bigint,
    usuario_id bigint, creado_por_id bigint, analisis_responsable_id bigint,
    responsable_cierre_id bigint, responsable_ti_id bigint, evaluador_id bigint,
    registrado_por_id bigint, subido_por_id bigint,
    numero integer, motivo text, fecha_inicio timestamptz, fecha_fin timestamptz,
    analisis_inicio timestamptz, analisis_fin timestamptz, causa_raiz text,
    checklist_snapshot jsonb, respuestas jsonb, control jsonb,
    fecha_cierre timestamptz, comentarios_cierre text, resultado_cierre varchar(12),
    numero_pbi varchar(100), ticket_incidente varchar(100), sistema varchar(200),
    herramienta varchar(100), estado varchar(30), fecha_creacion timestamptz,
    fecha_cierre_pbi date, observacion text,
    fecha_evaluacion date, resultado varchar(12), comentario text, fecha_registro timestamptz,
    destinatarios varchar(500), medio varchar(120), descripcion text, fecha timestamptz,
    accion_id bigint, analisis_id bigint, evaluacion_id bigint, cierre_id bigint,
    archivo varchar(100), nombre_original varchar(255), mime_type varchar(100),
    tamanio integer, fecha_carga timestamptz,
    fecha_hora timestamptz, accion varchar(70), estado_anterior varchar(30),
    estado_nuevo varchar(30), metadata_json jsonb,
    tipo varchar(50), titulo varchar(250), mensaje text, leida boolean, fecha_lectura timestamptz,
    entidad varchar(100), objeto varchar(100), antes jsonb, despues jsonb
);

INSERT INTO evento_nuevo
(id, registro_tipo, hallazgo_id, numero, motivo, creado_por_id, fecha_inicio, fecha_fin,
 analisis_responsable_id, analisis_inicio, analisis_fin, causa_raiz, checklist_snapshot,
 respuestas, control, responsable_cierre_id, fecha_cierre, comentarios_cierre, resultado_cierre)
SELECT id, 'CICLO_TRATAMIENTO', hallazgo_id, numero, motivo, creado_por_id, fecha_inicio, fecha_fin,
 analisis_responsable_id, analisis_inicio, analisis_fin, causa_raiz, checklist_snapshot,
 respuestas, control, responsable_cierre_id, fecha_cierre, comentarios_cierre, resultado_cierre
FROM hallazgos_ciclotratamiento;

INSERT INTO evento_nuevo
(id, registro_tipo, ciclo_id, numero_pbi, ticket_incidente, sistema, herramienta,
 responsable_ti_id, estado, fecha_creacion, fecha_cierre_pbi, observacion)
SELECT 20000000 + id, 'PBI', ciclo_id, numero_pbi, ticket_incidente, sistema, herramienta,
 responsable_ti_id, estado, fecha_creacion, fecha_cierre, observacion
FROM hallazgos_pbi;

INSERT INTO evento_nuevo
(id, registro_tipo, ciclo_id, evaluador_id, fecha_evaluacion, resultado, comentario, fecha_registro)
SELECT 30000000 + id, 'EVALUACION_EFICACIA', ciclo_id, evaluador_id, fecha_evaluacion, resultado, comentario, fecha_registro
FROM hallazgos_evaluacioneficacia;

INSERT INTO evento_nuevo
(id, registro_tipo, ciclo_id, registrado_por_id, destinatarios, medio, descripcion, fecha)
SELECT 40000000 + id, 'COMUNICACION', ciclo_id, registrado_por_id, destinatarios, medio, descripcion, fecha
FROM hallazgos_comunicacionhallazgo;

INSERT INTO evento_nuevo
(id, registro_tipo, hallazgo_id, accion_id, analisis_id, evaluacion_id, cierre_id,
 archivo, nombre_original, mime_type, tamanio, subido_por_id, fecha_carga, descripcion)
SELECT 50000000 + id, 'EVIDENCIA', hallazgo_id, accion_id, analisis_id,
 CASE WHEN evaluacion_id IS NULL THEN NULL ELSE 30000000 + evaluacion_id END,
 cierre_id, archivo, nombre_original, mime_type, tamanio, subido_por_id, fecha_carga, descripcion
FROM hallazgos_evidencia;

INSERT INTO evento_nuevo
(id, registro_tipo, accion_relacionada_id, hallazgo_id, usuario_id, fecha_hora,
 accion, estado_anterior, estado_nuevo, comentario, metadata_json)
SELECT 10000000 + id, 'HISTORIAL', accion_relacionada_id, hallazgo_id, usuario_id, fecha_hora,
 accion, estado_anterior, estado_nuevo, comentario, metadata_json
FROM hallazgos_historialhallazgo;

INSERT INTO evento_nuevo
(id, registro_tipo, usuario_id, hallazgo_id, tipo, titulo, mensaje, leida, fecha_creacion, fecha_lectura)
SELECT 60000000 + id, 'NOTIFICACION', usuario_id, hallazgo_id, tipo, titulo, mensaje, leida, fecha_creacion, fecha_lectura
FROM hallazgos_notificacion;

INSERT INTO evento_nuevo
(id, registro_tipo, usuario_id, fecha, entidad, objeto, accion, antes, despues)
SELECT 70000000 + id, 'AUDITORIA_ADMINISTRACION', usuario_id, fecha, entidad, objeto, accion, antes, despues
FROM catalogos_auditoriaadministracion;

-- 4. Actualiza referencias a los nuevos identificadores globales de configuración.
DO $$ DECLARE r record; BEGIN
  FOR r IN
    SELECT conname FROM pg_constraint
    WHERE conrelid='hallazgos_hallazgo'::regclass
      AND confrelid='catalogos_proceso'::regclass
  LOOP
    EXECUTE format('ALTER TABLE hallazgos_hallazgo DROP CONSTRAINT %%I', r.conname);
  END LOOP;
END $$;
UPDATE hallazgos_hallazgo SET proceso_id = 1000000 + proceso_id;
UPDATE hallazgos_hallazgo SET subproceso_id = 2000000 + subproceso_id WHERE subproceso_id IS NOT NULL;

-- 5. Elimina todas las vistas y mecanismos de compatibilidad.
DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT schemaname, viewname FROM pg_views WHERE schemaname='public' LOOP
    EXECUTE format('DROP VIEW IF EXISTS %%I.%%I CASCADE', r.schemaname, r.viewname);
  END LOOP;
END $$;
DROP FUNCTION IF EXISTS sistema_registro_auxiliar_dml() CASCADE;
DO $$ DECLARE r record; BEGIN
  FOR r IN
    SELECT t.typname FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
    WHERE n.nspname='public' AND left(t.typname, 5) = '_aux_'
  LOOP
    EXECUTE format('DROP TYPE IF EXISTS %%I CASCADE', r.typname);
  END LOOP;
END $$;

-- 6. Retira las tablas sustituidas y adopta los nombres definitivos.
DROP TABLE IF EXISTS catalogos_catalogo CASCADE;
DROP TABLE IF EXISTS catalogos_proceso CASCADE;
DROP TABLE IF EXISTS hallazgos_ciclotratamiento CASCADE;
DROP TABLE IF EXISTS hallazgos_historialhallazgo CASCADE;
DROP TABLE IF EXISTS hallazgos_correlativosac CASCADE;
DROP TABLE IF EXISTS sistema_registro_auxiliar CASCADE;
ALTER TABLE accounts_usuario RENAME TO usuario;
ALTER TABLE hallazgos_hallazgo RENAME TO registro_general;
ALTER TABLE hallazgos_accion RENAME TO actividad;
ALTER TABLE configuracion_nueva RENAME TO configuracion;
ALTER TABLE evento_nuevo RENAME TO evento;

-- 7. Índices y relaciones físicas esenciales (no son objetos de negocio adicionales).
CREATE UNIQUE INDEX configuracion_catalogo_codigo_uq ON configuracion(clase, codigo) WHERE registro_tipo='CATALOGO';
CREATE UNIQUE INDEX configuracion_catalogo_valor_uq ON configuracion(clase, valor) WHERE registro_tipo='CATALOGO' AND valor IS NOT NULL;
CREATE UNIQUE INDEX configuracion_proceso_nombre_uq ON configuracion(nombre) WHERE registro_tipo='PROCESO';
CREATE UNIQUE INDEX configuracion_subproceso_uq ON configuracion(proceso_id, nombre) WHERE registro_tipo='SUBPROCESO';
CREATE UNIQUE INDEX configuracion_matriz_uq ON configuracion(impacto_id, urgencia_id) WHERE registro_tipo='MATRIZ_PRIORIDAD';
CREATE UNIQUE INDEX configuracion_pregunta_uq ON configuracion(codigo) WHERE registro_tipo='PREGUNTA_CAUSA';
CREATE UNIQUE INDEX configuracion_correlativo_uq ON configuracion(anio, ambito) WHERE registro_tipo='CORRELATIVO_SAC';
CREATE INDEX configuracion_tipo_idx ON configuracion(registro_tipo);
CREATE INDEX evento_tipo_idx ON evento(registro_tipo);
CREATE INDEX evento_hallazgo_idx ON evento(hallazgo_id);
CREATE INDEX evento_ciclo_idx ON evento(ciclo_id);
CREATE INDEX evento_usuario_idx ON evento(usuario_id);
CREATE INDEX evento_accion_idx ON evento(accion_relacionada_id);

ALTER TABLE registro_general ADD CONSTRAINT registro_tipo_fk FOREIGN KEY (tipo_registro_id) REFERENCES configuracion(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE registro_general ADD CONSTRAINT registro_fuente_fk FOREIGN KEY (fuente_deteccion_id) REFERENCES configuracion(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE registro_general ADD CONSTRAINT registro_proceso_fk FOREIGN KEY (proceso_id) REFERENCES configuracion(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE registro_general ADD CONSTRAINT registro_subproceso_fk FOREIGN KEY (subproceso_id) REFERENCES configuracion(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE registro_general ADD CONSTRAINT registro_urgencia_fk FOREIGN KEY (urgencia_id) REFERENCES configuracion(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE registro_general ADD CONSTRAINT registro_prioridad_fk FOREIGN KEY (prioridad_id) REFERENCES configuracion(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE actividad ADD CONSTRAINT actividad_ciclo_fk FOREIGN KEY (ciclo_id) REFERENCES evento(id) DEFERRABLE INITIALLY DEFERRED;

SELECT setval(pg_get_serial_sequence('configuracion','id'), GREATEST((SELECT COALESCE(MAX(id), 1) FROM configuracion), 1));
SELECT setval(pg_get_serial_sequence('evento','id'), GREATEST((SELECT COALESCE(MAX(id), 1) FROM evento), 1));
"""


def forwards(apps, schema_editor):
    schema_editor.execute(SQL)


class Migration(migrations.Migration):
    atomic = True
    dependencies = [("hallazgos", "0012_accion_inmediata_y_estados")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
