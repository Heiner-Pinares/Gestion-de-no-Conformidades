SET DEFINE OFF
SET SERVEROUTPUT ON SIZE UNLIMITED
SET ECHO ON
SET FEEDBACK ON
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

ALTER SESSION SET TIME_ZONE = 'UTC';

PROMPT ============================================================
PROMPT Portal NC - instalacion en USRFACT
PROMPT ============================================================

@@00_prevalidacion.sql
@@01_crear_tablas.sql
@@02_relaciones_indices.sql
@@03_triggers_integridad.sql
@@04_datos_base.sql
@@05_baseline_django.sql
@@06_ajustar_identidades.sql
@@07_permisos.sql
@@08_prueba_humo.sql
@@09_validacion_final.sql

PROMPT ============================================================
PROMPT INSTALACION COMPLETADA Y VALIDADA
PROMPT ============================================================

EXIT SUCCESS
