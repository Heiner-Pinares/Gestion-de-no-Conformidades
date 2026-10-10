PROMPT [0/9] Prevalidacion de Oracle y del esquema

DECLARE
    v_existentes        PLS_INTEGER;
    v_objetos           PLS_INTEGER;
    v_restricciones     PLS_INTEGER;
    v_usuarios          PLS_INTEGER;
    v_create_trigger    PLS_INTEGER;
    v_json              PLS_INTEGER;
    v_random            NUMBER;
    v_blob              BLOB;
BEGIN
    IF UPPER(USER) <> 'USRFACT' THEN
        RAISE_APPLICATION_ERROR(-20001,
            'Conectese como USRFACT. Usuario actual: ' || USER);
    END IF;

    IF DBMS_DB_VERSION.VERSION < 19 THEN
        RAISE_APPLICATION_ERROR(-20002,
            'Se requiere Oracle Database 19c o superior.');
    END IF;

    SELECT COUNT(*)
      INTO v_create_trigger
      FROM USER_SYS_PRIVS
     WHERE PRIVILEGE IN ('CREATE TRIGGER', 'CREATE ANY TRIGGER');

    IF v_create_trigger = 0 THEN
        RAISE_APPLICATION_ERROR(-20009,
            'Falta privilegio directo para crear triggers. El DBA debe ejecutar: GRANT CREATE TRIGGER TO USRFACT;');
    END IF;

    SELECT COUNT(*)
      INTO v_existentes
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

    IF v_existentes > 0 THEN
        RAISE_APPLICATION_ERROR(-20003,
            'Ya existen ' || v_existentes ||
            ' tablas del Portal NC. No se ejecutara una instalacion parcial.');
    END IF;

    SELECT COUNT(*)
      INTO v_objetos
      FROM USER_OBJECTS
     WHERE OBJECT_NAME LIKE 'IX\_%\_NC' ESCAPE '\'
        OR OBJECT_NAME LIKE 'UX\_%\_NC' ESCAPE '\'
        OR OBJECT_NAME LIKE 'TRG\_%\_NC' ESCAPE '\';

    SELECT COUNT(*)
      INTO v_restricciones
      FROM USER_CONSTRAINTS
     WHERE REGEXP_LIKE(CONSTRAINT_NAME, '^(PK|UK|CK|FK)_.+_NC$');

    IF v_objetos > 0 OR v_restricciones > 0 THEN
        RAISE_APPLICATION_ERROR(-20006,
            'Existen nombres de indices, triggers o restricciones reservados para Portal NC. Objetos=' ||
            v_objetos || ', restricciones=' || v_restricciones || '.');
    END IF;

    SELECT COUNT(*)
      INTO v_usuarios
      FROM ALL_USERS
     WHERE USERNAME = 'USRFACSOP';

    IF v_usuarios <> 1 THEN
        RAISE_APPLICATION_ERROR(-20004,
            'Debe existir USRFACSOP antes de instalar. Encontrados: ' || v_usuarios);
    END IF;

    -- Django y la prueba de archivos usan estos paquetes. Al estar aquí, una
    -- falta de EXECUTE detiene el instalador antes de crear objetos definitivos.
    v_random := SYS.DBMS_RANDOM.VALUE;
    SYS.DBMS_LOB.CREATETEMPORARY(v_blob, TRUE);
    SYS.DBMS_LOB.WRITEAPPEND(v_blob, 1, HEXTORAW('00'));
    SYS.DBMS_LOB.FREETEMPORARY(v_blob);

    -- Prueba efectiva de las capacidades requeridas. Verifica antes de crear
    -- las tablas definitivas: CREATE TABLE, cuota, nombres de más de 30 bytes
    -- (COMPATIBLE >= 12.2), CREATE TRIGGER y el tipo exacto que Django 5.2
    -- usa para JSONField en Oracle: NCLOB con restricción IS JSON.
    -- Los objetos temporales se eliminan inmediatamente.
    BEGIN
        EXECUTE IMMEDIATE q'[CREATE TABLE tbl_nc_prevalidacion_nombre_largo_123 (
            id NUMBER,
            clase NVARCHAR2(12),
            valor NUMBER(5),
            datos NCLOB,
            CONSTRAINT ck_nc_prevalidacion_json_123
                CHECK (datos IS JSON (STRICT))
        )]';
        EXECUTE IMMEDIATE q'[CREATE UNIQUE INDEX ux_nc_prevalidacion_valor_123
            ON tbl_nc_prevalidacion_nombre_largo_123 (
                CASE WHEN valor IS NOT NULL THEN clase END,
                CASE WHEN valor IS NOT NULL THEN valor END
            )]';
        EXECUTE IMMEDIATE q'~CREATE OR REPLACE TRIGGER trg_nc_prevalidacion_nombre_largo_123
            BEFORE INSERT OR UPDATE ON tbl_nc_prevalidacion_nombre_largo_123
            FOR EACH ROW
            BEGIN
                IF :NEW.datos IS NULL THEN
                    :NEW.datos := TO_NCLOB('{}');
                END IF;
            END;~';
        EXECUTE IMMEDIATE q'[INSERT INTO tbl_nc_prevalidacion_nombre_largo_123
            (id, clase, valor, datos)
            VALUES (1, 'CATEGORIA', NULL, TO_NCLOB('{"portal":"nc"}'))]';
        EXECUTE IMMEDIATE q'[INSERT INTO tbl_nc_prevalidacion_nombre_largo_123
            (id, clase, valor, datos) VALUES (2, 'CATEGORIA', NULL, NULL)]';
        EXECUTE IMMEDIATE q'[INSERT INTO tbl_nc_prevalidacion_nombre_largo_123
            (id, clase, valor, datos) VALUES (3, 'IMPACTO', 1, NULL)]';
        BEGIN
            EXECUTE IMMEDIATE q'[INSERT INTO tbl_nc_prevalidacion_nombre_largo_123
                (id, clase, valor, datos) VALUES (4, 'IMPACTO', 1, NULL)]';
            RAISE_APPLICATION_ERROR(-20008,
                'El indice condicional no rechazo el valor no nulo duplicado.');
        EXCEPTION
            WHEN DUP_VAL_ON_INDEX THEN NULL;
        END;
        EXECUTE IMMEDIATE q'[UPDATE tbl_nc_prevalidacion_nombre_largo_123
            SET datos = NULL WHERE id = 1]';
        EXECUTE IMMEDIATE q'[SELECT COUNT(*)
            FROM tbl_nc_prevalidacion_nombre_largo_123
            WHERE datos IS JSON (STRICT)]' INTO v_json;
        IF v_json <> 3 THEN
            RAISE_APPLICATION_ERROR(-20007,
                'La prueba NCLOB/trigger no devolvio los tres registros JSON esperados.');
        END IF;
        EXECUTE IMMEDIATE 'DROP TABLE tbl_nc_prevalidacion_nombre_largo_123 PURGE';
    EXCEPTION
        WHEN OTHERS THEN
            BEGIN
                EXECUTE IMMEDIATE 'DROP TABLE tbl_nc_prevalidacion_nombre_largo_123 PURGE';
            EXCEPTION
                WHEN OTHERS THEN NULL;
            END;
            RAISE_APPLICATION_ERROR(-20005,
                'USRFACT no supera la prevalidacion DDL/JSON. Revise CREATE TABLE, CREATE INDEX funcional, CREATE TRIGGER, cuota, COMPATIBLE >= 12.2 y NCLOB IS JSON. Detalle: ' || SQLERRM);
    END;

    DBMS_OUTPUT.PUT_LINE('OK: usuario=' || USER ||
                         ', Oracle=' || DBMS_DB_VERSION.VERSION || '.' || DBMS_DB_VERSION.RELEASE ||
                         ', usuario destino=USRFACSOP, tablas previas=0, DDL, indice condicional, trigger NCLOB y JSON verificados.');
END;
/
