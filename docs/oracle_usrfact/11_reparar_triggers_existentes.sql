-- Reparación idempotente de los triggers del Portal NC ya instalado.
-- Ejecutar conectado como USRFACT después de que el DBA conceda temporalmente:
-- GRANT CREATE TRIGGER TO USRFACT;
SET DEFINE OFF
SET SERVEROUTPUT ON SIZE UNLIMITED
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

DECLARE
    v_tablas      PLS_INTEGER;
    v_privilegio  PLS_INTEGER;
BEGIN
    IF UPPER(USER) <> 'USRFACT' THEN
        RAISE_APPLICATION_ERROR(-20501,
            'Conectese como USRFACT. Usuario actual: ' || USER);
    END IF;

    SELECT COUNT(*) INTO v_tablas
      FROM USER_TABLES
     WHERE TABLE_NAME IN (
        'TBL_USUARIO_NC','TBL_USUARIO_ROL_NC','TBL_CATALOGO_NC',
        'TBL_PROCESO_NC','TBL_PROCESO_VALIDADOR_NC','TBL_SUBPROCESO_NC',
        'TBL_MATRIZ_PRIORIDAD_NC','TBL_CONFIGURACION_IMPACTO_NC',
        'TBL_CONFIGURACION_URGENCIA_NC','TBL_PREGUNTA_CAUSA_NC',
        'TBL_AUDITORIA_ADMINISTRACION_NC','TBL_CORRELATIVO_SAC_NC',
        'TBL_REGISTRO_GENERAL_NC','TBL_CICLO_TRATAMIENTO_NC',
        'TBL_ACTIVIDAD_NC','TBL_PBI_NC','TBL_EVALUACION_EFICACIA_NC',
        'TBL_COMUNICACION_NC','TBL_EVIDENCIA_NC','TBL_ARCHIVO_EVIDENCIA_NC',
        'TBL_HISTORIAL_HALLAZGO_NC','TBL_NOTIFICACION_NC',
        'TBL_DJANGO_MIGRATIONS_NC','TBL_DJANGO_SESSION_NC'
     );
    IF v_tablas <> 24 THEN
        RAISE_APPLICATION_ERROR(-20502,
            'Se esperaban 24 tablas del Portal NC y existen ' || v_tablas || '.');
    END IF;

    SELECT COUNT(*) INTO v_privilegio
      FROM USER_SYS_PRIVS
     WHERE PRIVILEGE IN ('CREATE TRIGGER', 'CREATE ANY TRIGGER');
    IF v_privilegio = 0 THEN
        RAISE_APPLICATION_ERROR(-20503,
            'Falta privilegio directo. El DBA debe ejecutar: GRANT CREATE TRIGGER TO USRFACT;');
    END IF;
END;
/

PROMPT [3/9] Creacion de triggers de integridad y sincronizacion

CREATE OR REPLACE TRIGGER trg_usuario_json_nc
BEFORE INSERT OR UPDATE ON tbl_usuario_nc
FOR EACH ROW
BEGIN
    IF :NEW.roles IS NULL THEN
        :NEW.roles := TO_NCLOB('[]');
    END IF;
END;
/

CREATE OR REPLACE TRIGGER trg_usuario_roles_sync_nc
AFTER INSERT OR UPDATE ON tbl_usuario_nc
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
BEFORE INSERT OR UPDATE ON tbl_proceso_nc
FOR EACH ROW
BEGIN
    IF :NEW.validadores_ids IS NULL THEN
        :NEW.validadores_ids := TO_NCLOB('[]');
    END IF;
END;
/

CREATE OR REPLACE TRIGGER trg_proceso_valid_sync_nc
AFTER INSERT OR UPDATE ON tbl_proceso_nc
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
BEFORE INSERT OR UPDATE ON tbl_auditoria_administracion_nc
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
BEFORE INSERT OR UPDATE ON tbl_ciclo_tratamiento_nc
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
BEFORE INSERT OR UPDATE ON tbl_historial_hallazgo_nc
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


DECLARE
    v_total       PLS_INTEGER;
    v_invalidos   PLS_INTEGER;
    v_deshabilitados PLS_INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_total
      FROM USER_TRIGGERS
     WHERE TRIGGER_NAME IN (
        'TRG_USUARIO_JSON_NC','TRG_USUARIO_ROLES_SYNC_NC',
        'TRG_PROCESO_JSON_NC','TRG_PROCESO_VALID_SYNC_NC',
        'TRG_AUDITORIA_JSON_NC','TRG_CICLO_JSON_NC',
        'TRG_HISTORIAL_JSON_NC','TRG_MATRIZ_CATALOGOS_NC',
        'TRG_REGISTRO_CATALOGOS_NC','TRG_REGISTRO_UPDATED_NC',
        'TRG_ACTIVIDAD_UPDATED_NC'
     );
    IF v_total <> 11 THEN
        RAISE_APPLICATION_ERROR(-20504,
            'Se esperaban 11 triggers y existen ' || v_total || '.');
    END IF;

    SELECT COUNT(*) INTO v_invalidos
      FROM USER_OBJECTS
     WHERE OBJECT_TYPE = 'TRIGGER'
       AND OBJECT_NAME IN (
        'TRG_USUARIO_JSON_NC','TRG_USUARIO_ROLES_SYNC_NC',
        'TRG_PROCESO_JSON_NC','TRG_PROCESO_VALID_SYNC_NC',
        'TRG_AUDITORIA_JSON_NC','TRG_CICLO_JSON_NC',
        'TRG_HISTORIAL_JSON_NC','TRG_MATRIZ_CATALOGOS_NC',
        'TRG_REGISTRO_CATALOGOS_NC','TRG_REGISTRO_UPDATED_NC',
        'TRG_ACTIVIDAD_UPDATED_NC'
       )
       AND STATUS <> 'VALID';
    IF v_invalidos <> 0 THEN
        RAISE_APPLICATION_ERROR(-20505,
            'Hay ' || v_invalidos || ' triggers invalidos.');
    END IF;

    SELECT COUNT(*) INTO v_deshabilitados
      FROM USER_TRIGGERS
     WHERE TRIGGER_NAME IN (
        'TRG_USUARIO_JSON_NC','TRG_USUARIO_ROLES_SYNC_NC',
        'TRG_PROCESO_JSON_NC','TRG_PROCESO_VALID_SYNC_NC',
        'TRG_AUDITORIA_JSON_NC','TRG_CICLO_JSON_NC',
        'TRG_HISTORIAL_JSON_NC','TRG_MATRIZ_CATALOGOS_NC',
        'TRG_REGISTRO_CATALOGOS_NC','TRG_REGISTRO_UPDATED_NC',
        'TRG_ACTIVIDAD_UPDATED_NC'
       )
       AND STATUS <> 'ENABLED';
    IF v_deshabilitados <> 0 THEN
        RAISE_APPLICATION_ERROR(-20506,
            'Hay ' || v_deshabilitados || ' triggers deshabilitados.');
    END IF;

    DBMS_OUTPUT.PUT_LINE('OK: 11 triggers validos y habilitados.');
END;
/

-- Después de validar, el DBA puede ejecutar:
-- REVOKE CREATE TRIGGER FROM USRFACT;
EXIT SUCCESS
