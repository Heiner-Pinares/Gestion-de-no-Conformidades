PROMPT [0/9] Prevalidacion de Oracle y del esquema

DECLARE
    v_existentes        PLS_INTEGER;
    v_objetos           PLS_INTEGER;
    v_restricciones     PLS_INTEGER;
    v_usuarios          PLS_INTEGER;
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
     WHERE USERNAME IN ('C27826','C28111','C28134');

    IF v_usuarios <> 3 THEN
        RAISE_APPLICATION_ERROR(-20004,
            'Deben existir C27826, C28111 y C28134 antes de instalar. Encontrados: ' || v_usuarios);
    END IF;

    -- Django y la prueba de archivos usan estos paquetes. Al estar aquí, una
    -- falta de EXECUTE detiene el instalador antes de crear objetos definitivos.
    v_random := SYS.DBMS_RANDOM.VALUE;
    SYS.DBMS_LOB.CREATETEMPORARY(v_blob, TRUE);
    SYS.DBMS_LOB.WRITEAPPEND(v_blob, 1, HEXTORAW('00'));
    SYS.DBMS_LOB.FREETEMPORARY(v_blob);

    -- Prueba efectiva de las capacidades requeridas. Verifica en una sola
    -- operación CREATE TABLE, cuota, nombres de más de 30 bytes (COMPATIBLE
    -- >= 12.2) y CREATE TRIGGER. Los objetos se eliminan inmediatamente.
    BEGIN
        EXECUTE IMMEDIATE
            'CREATE TABLE tbl_nc_prevalidacion_nombre_largo_123 (id NUMBER)';
        EXECUTE IMMEDIATE q'[CREATE OR REPLACE TRIGGER trg_nc_prevalidacion_nombre_largo_123
            BEFORE INSERT ON tbl_nc_prevalidacion_nombre_largo_123
            BEGIN
                NULL;
            END;]';
        EXECUTE IMMEDIATE 'DROP TABLE tbl_nc_prevalidacion_nombre_largo_123 PURGE';
    EXCEPTION
        WHEN OTHERS THEN
            BEGIN
                EXECUTE IMMEDIATE 'DROP TABLE tbl_nc_prevalidacion_nombre_largo_123 PURGE';
            EXCEPTION
                WHEN OTHERS THEN NULL;
            END;
            RAISE_APPLICATION_ERROR(-20005,
                'USRFACT no puede crear las tablas/triggers requeridos. Revise CREATE TABLE, CREATE TRIGGER, cuota y COMPATIBLE >= 12.2. Detalle: ' || SQLERRM);
    END;

    DBMS_OUTPUT.PUT_LINE('OK: usuario=' || USER ||
                         ', Oracle=' || DBMS_DB_VERSION.VERSION || '.' || DBMS_DB_VERSION.RELEASE ||
                         ', usuarios destino=3, tablas previas=0 y capacidades DDL verificadas.');
END;
/
