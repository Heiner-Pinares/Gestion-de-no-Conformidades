-- SOLO PARA AMBIENTES DESCARTABLES.
-- Borra íntegramente el esquema funcional creado por este paquete.
SET SERVEROUTPUT ON
SET DEFINE OFF
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

DECLARE
    PROCEDURE borrar(p_tabla VARCHAR2) IS
    BEGIN
        EXECUTE IMMEDIATE 'DROP TABLE ' || DBMS_ASSERT.SIMPLE_SQL_NAME(p_tabla) ||
                          ' CASCADE CONSTRAINTS PURGE';
        DBMS_OUTPUT.PUT_LINE('Eliminada: ' || p_tabla);
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLCODE <> -942 THEN
                RAISE;
            END IF;
    END;
BEGIN
    borrar('TBL_ARCHIVO_EVIDENCIA_NC');
    borrar('TBL_EVIDENCIA_NC');
    borrar('TBL_NOTIFICACION_NC');
    borrar('TBL_HISTORIAL_HALLAZGO_NC');
    borrar('TBL_COMUNICACION_NC');
    borrar('TBL_EVALUACION_EFICACIA_NC');
    borrar('TBL_PBI_NC');
    borrar('TBL_ACTIVIDAD_NC');
    borrar('TBL_CICLO_TRATAMIENTO_NC');
    borrar('TBL_REGISTRO_GENERAL_NC');
    borrar('TBL_CORRELATIVO_SAC_NC');
    borrar('TBL_AUDITORIA_ADMINISTRACION_NC');
    borrar('TBL_PREGUNTA_CAUSA_NC');
    borrar('TBL_MATRIZ_PRIORIDAD_NC');
    borrar('TBL_CONFIGURACION_URGENCIA_NC');
    borrar('TBL_CONFIGURACION_IMPACTO_NC');
    borrar('TBL_SUBPROCESO_NC');
    borrar('TBL_PROCESO_VALIDADOR_NC');
    borrar('TBL_PROCESO_NC');
    borrar('TBL_CATALOGO_NC');
    borrar('TBL_USUARIO_ROL_NC');
    borrar('TBL_USUARIO_NC');
    borrar('TBL_DJANGO_SESSION_NC');
    borrar('TBL_DJANGO_MIGRATIONS_NC');
END;
/

PROMPT Esquema funcional del Portal NC eliminado.
