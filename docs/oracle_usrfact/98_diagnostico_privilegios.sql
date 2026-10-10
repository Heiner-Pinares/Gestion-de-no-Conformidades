-- Diagnostico de solo lectura. No crea ni modifica objetos.
-- Ejecutar conectado como USRFACT antes de instalar.
SET SERVEROUTPUT ON
SET DEFINE OFF

DECLARE
    v_trigger PLS_INTEGER;
    v_table   PLS_INTEGER;
BEGIN
    DBMS_OUTPUT.PUT_LINE('Usuario actual: ' || USER);
    DBMS_OUTPUT.PUT_LINE('Oracle: ' || DBMS_DB_VERSION.VERSION || '.' || DBMS_DB_VERSION.RELEASE);

    SELECT COUNT(*) INTO v_table
      FROM USER_SYS_PRIVS
     WHERE PRIVILEGE IN ('CREATE TABLE', 'CREATE ANY TABLE');

    SELECT COUNT(*) INTO v_trigger
      FROM USER_SYS_PRIVS
     WHERE PRIVILEGE IN ('CREATE TRIGGER', 'CREATE ANY TRIGGER');

    IF v_table = 0 THEN
        DBMS_OUTPUT.PUT_LINE('FALTA: privilegio directo CREATE TABLE para USRFACT.');
    ELSE
        DBMS_OUTPUT.PUT_LINE('OK: USRFACT tiene privilegio directo para crear tablas.');
    END IF;

    IF v_trigger = 0 THEN
        DBMS_OUTPUT.PUT_LINE('FALTA: GRANT CREATE TRIGGER TO USRFACT;');
    ELSE
        DBMS_OUTPUT.PUT_LINE('OK: USRFACT tiene privilegio directo para crear triggers.');
    END IF;
END;
/

SELECT TABLESPACE_NAME, BYTES, MAX_BYTES
  FROM USER_TS_QUOTAS
 ORDER BY TABLESPACE_NAME;

SELECT USERNAME
  FROM ALL_USERS
 WHERE USERNAME IN ('C27826', 'C28111', 'C28134')
 ORDER BY USERNAME;
