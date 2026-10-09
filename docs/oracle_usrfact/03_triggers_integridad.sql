PROMPT [3/9] Creacion de triggers de integridad y sincronizacion

CREATE OR REPLACE TRIGGER trg_usuario_json_nc
BEFORE INSERT OR UPDATE OF roles ON tbl_usuario_nc
FOR EACH ROW
BEGIN
    IF :NEW.roles IS NULL THEN
        :NEW.roles := TO_NCLOB('[]');
    END IF;
END;
/

CREATE OR REPLACE TRIGGER trg_usuario_roles_sync_nc
AFTER INSERT OR UPDATE OF roles ON tbl_usuario_nc
FOR EACH ROW
BEGIN
    DELETE FROM tbl_usuario_rol_nc WHERE usuario_id = :NEW.id;

    INSERT INTO tbl_usuario_rol_nc (usuario_id, rol)
    SELECT :NEW.id, roles_json.rol
      FROM (
        SELECT DISTINCT jt.rol
          FROM JSON_TABLE(
                 :NEW.roles,
                 '$[*]' COLUMNS (rol VARCHAR2(20) PATH '$')
               ) jt
         WHERE jt.rol IN ('USUARIO', 'VALIDADOR', 'ADMINISTRADOR')
      ) roles_json;
END;
/

CREATE OR REPLACE TRIGGER trg_proceso_json_nc
BEFORE INSERT OR UPDATE OF validadores_ids ON tbl_proceso_nc
FOR EACH ROW
BEGIN
    IF :NEW.validadores_ids IS NULL THEN
        :NEW.validadores_ids := TO_NCLOB('[]');
    END IF;
END;
/

CREATE OR REPLACE TRIGGER trg_proceso_valid_sync_nc
AFTER INSERT OR UPDATE OF validadores_ids ON tbl_proceso_nc
FOR EACH ROW
BEGIN
    DELETE FROM tbl_proceso_validador_nc WHERE proceso_id = :NEW.id;

    INSERT INTO tbl_proceso_validador_nc (proceso_id, usuario_id)
    SELECT :NEW.id, validadores.usuario_id
      FROM (
        SELECT DISTINCT jt.usuario_id
          FROM JSON_TABLE(
                 :NEW.validadores_ids,
                 '$[*]' COLUMNS (usuario_id NUMBER(19) PATH '$')
               ) jt
          JOIN tbl_usuario_nc u ON u.id = jt.usuario_id
      ) validadores;
END;
/

CREATE OR REPLACE TRIGGER trg_auditoria_json_nc
BEFORE INSERT OR UPDATE OF antes, despues ON tbl_auditoria_administracion_nc
FOR EACH ROW
BEGIN
    IF :NEW.antes IS NULL THEN
        :NEW.antes := TO_NCLOB('{}');
    END IF;
    IF :NEW.despues IS NULL THEN
        :NEW.despues := TO_NCLOB('{}');
    END IF;
END;
/

CREATE OR REPLACE TRIGGER trg_ciclo_json_nc
BEFORE INSERT OR UPDATE OF checklist_snapshot, respuestas, control
ON tbl_ciclo_tratamiento_nc
FOR EACH ROW
BEGIN
    IF :NEW.checklist_snapshot IS NULL THEN
        :NEW.checklist_snapshot := TO_NCLOB('[]');
    END IF;
    IF :NEW.respuestas IS NULL THEN
        :NEW.respuestas := TO_NCLOB('[]');
    END IF;
    IF :NEW.control IS NULL THEN
        :NEW.control := TO_NCLOB('{}');
    END IF;
END;
/

CREATE OR REPLACE TRIGGER trg_historial_json_nc
BEFORE INSERT OR UPDATE OF metadata_json ON tbl_historial_hallazgo_nc
FOR EACH ROW
BEGIN
    IF :NEW.metadata_json IS NULL THEN
        :NEW.metadata_json := TO_NCLOB('{}');
    END IF;
END;
/

CREATE OR REPLACE TRIGGER trg_matriz_catalogos_nc
BEFORE INSERT OR UPDATE OF impacto_id, urgencia_id, prioridad_id
ON tbl_matriz_prioridad_nc
FOR EACH ROW
DECLARE
    v_ok PLS_INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_ok FROM tbl_catalogo_nc
     WHERE id = :NEW.impacto_id AND clase = 'IMPACTO';
    IF v_ok <> 1 THEN
        RAISE_APPLICATION_ERROR(-20101, 'impacto_id no pertenece al catalogo IMPACTO.');
    END IF;

    SELECT COUNT(*) INTO v_ok FROM tbl_catalogo_nc
     WHERE id = :NEW.urgencia_id AND clase = 'URGENCIA';
    IF v_ok <> 1 THEN
        RAISE_APPLICATION_ERROR(-20102, 'urgencia_id no pertenece al catalogo URGENCIA.');
    END IF;

    SELECT COUNT(*) INTO v_ok FROM tbl_catalogo_nc
     WHERE id = :NEW.prioridad_id AND clase = 'PRIORIDAD';
    IF v_ok <> 1 THEN
        RAISE_APPLICATION_ERROR(-20103, 'prioridad_id no pertenece al catalogo PRIORIDAD.');
    END IF;
END;
/

CREATE OR REPLACE TRIGGER trg_registro_catalogos_nc
BEFORE INSERT OR UPDATE OF tipo_registro_id, fuente_deteccion_id, urgencia_id, prioridad_id
ON tbl_registro_general_nc
FOR EACH ROW
DECLARE
    v_ok PLS_INTEGER;

    PROCEDURE validar(p_id NUMBER, p_clase VARCHAR2, p_campo VARCHAR2) IS
    BEGIN
        IF p_id IS NOT NULL THEN
            SELECT COUNT(*) INTO v_ok FROM tbl_catalogo_nc
             WHERE id = p_id AND clase = p_clase;
            IF v_ok <> 1 THEN
                RAISE_APPLICATION_ERROR(-20110,
                    p_campo || ' no pertenece al catalogo ' || p_clase || '.');
            END IF;
        END IF;
    END;
BEGIN
    validar(:NEW.tipo_registro_id, 'TIPO', 'tipo_registro_id');
    validar(:NEW.fuente_deteccion_id, 'FUENTE', 'fuente_deteccion_id');
    validar(:NEW.urgencia_id, 'URGENCIA', 'urgencia_id');
    validar(:NEW.prioridad_id, 'PRIORIDAD', 'prioridad_id');
END;
/

CREATE OR REPLACE TRIGGER trg_registro_updated_nc
BEFORE UPDATE ON tbl_registro_general_nc
FOR EACH ROW
BEGIN
    :NEW.updated_at := LOCALTIMESTAMP;
END;
/

CREATE OR REPLACE TRIGGER trg_actividad_updated_nc
BEFORE UPDATE ON tbl_actividad_nc
FOR EACH ROW
BEGIN
    :NEW.updated_at := LOCALTIMESTAMP;
END;
/

PROMPT OK: triggers JSON, catalogos, roles y validadores creados.
