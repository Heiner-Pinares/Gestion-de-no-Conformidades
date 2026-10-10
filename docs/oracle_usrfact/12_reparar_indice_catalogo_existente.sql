-- Reparación idempotente para instalaciones creadas con la restricción
-- incorrecta UK_CAT_CLASE_VALOR_NC UNIQUE (clase, valor).
-- Ejecutar conectado como USRFACT. No elimina datos ni modifica columnas.
SET DEFINE OFF
SET SERVEROUTPUT ON SIZE UNLIMITED
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

DECLARE
    v_tabla PLS_INTEGER;
BEGIN
    IF UPPER(USER) <> 'USRFACT' THEN
        RAISE_APPLICATION_ERROR(-20601,
            'Conectese como USRFACT. Usuario actual: ' || USER);
    END IF;

    SELECT COUNT(*) INTO v_tabla
      FROM USER_TABLES
     WHERE TABLE_NAME = 'TBL_CATALOGO_NC';
    IF v_tabla <> 1 THEN
        RAISE_APPLICATION_ERROR(-20602,
            'No existe USRFACT.TBL_CATALOGO_NC.');
    END IF;
END;
/

DECLARE
    v_total PLS_INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_total
      FROM USER_CONSTRAINTS
     WHERE TABLE_NAME = 'TBL_CATALOGO_NC'
       AND CONSTRAINT_NAME = 'UK_CAT_CLASE_VALOR_NC';
    IF v_total = 1 THEN
        EXECUTE IMMEDIATE
            'ALTER TABLE tbl_catalogo_nc DROP CONSTRAINT uk_cat_clase_valor_nc';
        DBMS_OUTPUT.PUT_LINE('OK: restriccion incorrecta UK_CAT_CLASE_VALOR_NC eliminada.');
    END IF;

    SELECT COUNT(*) INTO v_total
      FROM USER_INDEXES
     WHERE INDEX_NAME = 'UK_CAT_CLASE_VALOR_NC';
    IF v_total = 1 THEN
        EXECUTE IMMEDIATE 'DROP INDEX uk_cat_clase_valor_nc';
    END IF;

    SELECT COUNT(*) INTO v_total
      FROM USER_INDEXES
     WHERE INDEX_NAME = 'UX_CAT_CLASE_VALOR_NC';
    IF v_total = 1 THEN
        EXECUTE IMMEDIATE 'DROP INDEX ux_cat_clase_valor_nc';
    END IF;

    EXECUTE IMMEDIATE q'~
        CREATE UNIQUE INDEX ux_cat_clase_valor_nc
            ON tbl_catalogo_nc (
                CASE WHEN valor IS NOT NULL THEN clase END,
                CASE WHEN valor IS NOT NULL THEN valor END
            )~';
    DBMS_OUTPUT.PUT_LINE('OK: indice condicional UX_CAT_CLASE_VALOR_NC creado.');
END;
/

-- Prueba real y reversible: dos filas de la misma clase con VALOR NULL deben coexistir.
DECLARE
    v_sufijo VARCHAR2(12) := SUBSTR(RAWTOHEX(SYS_GUID()), 1, 12);
BEGIN
    SAVEPOINT prueba_catalogo_null;

    INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
    VALUES ('TIPO', 'ZZ1_' || v_sufijo, 'Prueba temporal 1', 1, NULL, 9998);

    INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
    VALUES ('TIPO', 'ZZ2_' || v_sufijo, 'Prueba temporal 2', 1, NULL, 9999);

    ROLLBACK TO prueba_catalogo_null;
    DBMS_OUTPUT.PUT_LINE('OK: multiples valores NULL por clase comprobados sin conservar datos de prueba.');
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK TO prueba_catalogo_null;
        RAISE;
END;
/

DECLARE
    v_restriccion PLS_INTEGER;
    v_indice      PLS_INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_restriccion
      FROM USER_CONSTRAINTS
     WHERE TABLE_NAME = 'TBL_CATALOGO_NC'
       AND CONSTRAINT_NAME = 'UK_CAT_CLASE_VALOR_NC';

    SELECT COUNT(*) INTO v_indice
      FROM USER_INDEXES
     WHERE TABLE_NAME = 'TBL_CATALOGO_NC'
       AND INDEX_NAME = 'UX_CAT_CLASE_VALOR_NC'
       AND UNIQUENESS = 'UNIQUE'
       AND STATUS = 'VALID';

    IF v_restriccion <> 0 OR v_indice <> 1 THEN
        RAISE_APPLICATION_ERROR(-20603,
            'La reparacion del indice de catalogo no quedo valida.');
    END IF;

    DBMS_OUTPUT.PUT_LINE('REPARACION COMPLETADA: el catalogo acepta multiples NULL y conserva unicidad de valores numericos.');
END;
/
