PROMPT [9/9] Validacion final de la instalacion

DECLARE
    v_total       PLS_INTEGER;
    v_invalidos   PLS_INTEGER;
    v_max_id      NUMBER;
    v_seq_next    NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_total
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
    IF v_total <> 24 THEN
        RAISE_APPLICATION_ERROR(-20301, 'Se esperaban 24 tablas y existen ' || v_total || '.');
    END IF;

    SELECT COUNT(*) INTO v_total
      FROM USER_CONSTRAINTS
     WHERE CONSTRAINT_TYPE = 'R'
       AND TABLE_NAME LIKE 'TBL\_%\_NC' ESCAPE '\';
    IF v_total <> 44 THEN
        RAISE_APPLICATION_ERROR(-20302, 'Se esperaban 44 relaciones FK y existen ' || v_total || '.');
    END IF;

    SELECT COUNT(*) INTO v_total
      FROM USER_TAB_IDENTITY_COLS
     WHERE TABLE_NAME LIKE 'TBL\_%\_NC' ESCAPE '\';
    IF v_total <> 22 THEN
        RAISE_APPLICATION_ERROR(-20303, 'Se esperaban 22 identidades y existen ' || v_total || '.');
    END IF;

    FOR r IN (
        SELECT TABLE_NAME, COLUMN_NAME, SEQUENCE_NAME
          FROM USER_TAB_IDENTITY_COLS
         WHERE TABLE_NAME LIKE 'TBL\_%\_NC' ESCAPE '\'
    ) LOOP
        EXECUTE IMMEDIATE
            'SELECT NVL(MAX(' || r.COLUMN_NAME || '), 0) FROM ' || r.TABLE_NAME
            INTO v_max_id;
        SELECT LAST_NUMBER INTO v_seq_next
          FROM USER_SEQUENCES
         WHERE SEQUENCE_NAME = r.SEQUENCE_NAME;
        IF v_seq_next <= v_max_id THEN
            RAISE_APPLICATION_ERROR(-20316,
                'Identidad no ajustada: ' || r.TABLE_NAME ||
                ', MAX=' || v_max_id || ', siguiente=' || v_seq_next || '.');
        END IF;
    END LOOP;

    SELECT COUNT(*) INTO v_total
      FROM USER_INDEXES
     WHERE INDEX_NAME LIKE 'IX\_%\_NC' ESCAPE '\'
        OR INDEX_NAME LIKE 'UX\_%\_NC' ESCAPE '\';
    IF v_total <> 40 THEN
        RAISE_APPLICATION_ERROR(-20304, 'Se esperaban 40 indices explícitos y existen ' || v_total || '.');
    END IF;

    SELECT COUNT(*) INTO v_total
      FROM USER_TRIGGERS
     WHERE TRIGGER_NAME LIKE 'TRG\_%\_NC' ESCAPE '\';
    IF v_total <> 11 THEN
        RAISE_APPLICATION_ERROR(-20305, 'Se esperaban 11 triggers y existen ' || v_total || '.');
    END IF;

    SELECT COUNT(*) INTO v_invalidos
      FROM USER_CONSTRAINTS
     WHERE TABLE_NAME LIKE 'TBL\_%\_NC' ESCAPE '\'
       AND (STATUS <> 'ENABLED' OR VALIDATED <> 'VALIDATED');
    IF v_invalidos <> 0 THEN
        RAISE_APPLICATION_ERROR(-20306, 'Hay ' || v_invalidos || ' restricciones no validadas.');
    END IF;

    SELECT COUNT(*) INTO v_invalidos
      FROM USER_OBJECTS
     WHERE OBJECT_NAME LIKE 'TRG\_%\_NC' ESCAPE '\'
       AND STATUS <> 'VALID';
    IF v_invalidos <> 0 THEN
        RAISE_APPLICATION_ERROR(-20307, 'Hay ' || v_invalidos || ' triggers inválidos.');
    END IF;

    SELECT COUNT(*) INTO v_total FROM tbl_catalogo_nc;
    IF v_total <> 29 THEN
        RAISE_APPLICATION_ERROR(-20308, 'Se esperaban 29 valores de catálogo.');
    END IF;

    SELECT COUNT(*) INTO v_total FROM tbl_configuracion_impacto_nc;
    IF v_total <> 1 THEN
        RAISE_APPLICATION_ERROR(-20309, 'Debe existir una configuración de impacto.');
    END IF;

    SELECT COUNT(*) INTO v_total FROM tbl_configuracion_urgencia_nc;
    IF v_total <> 2 THEN
        RAISE_APPLICATION_ERROR(-20310, 'Deben existir dos configuraciones de urgencia.');
    END IF;

    SELECT COUNT(*) INTO v_total FROM tbl_matriz_prioridad_nc;
    IF v_total <> 9 THEN
        RAISE_APPLICATION_ERROR(-20311, 'La matriz de prioridad debe tener 9 combinaciones.');
    END IF;

    SELECT COUNT(*) INTO v_total FROM tbl_pregunta_causa_nc;
    IF v_total <> 32 THEN
        RAISE_APPLICATION_ERROR(-20312, 'La matriz 6M debe tener 32 preguntas.');
    END IF;

    SELECT COUNT(*) INTO v_total FROM tbl_django_migrations_nc;
    IF v_total <> 56 THEN
        RAISE_APPLICATION_ERROR(-20315,
            'La linea base Django debe contener 56 migraciones y contiene ' || v_total || '.');
    END IF;

    SELECT COUNT(*) INTO v_total
      FROM USER_TAB_PRIVS_MADE
     WHERE GRANTEE IN ('C27826','C28111','C28134')
       AND PRIVILEGE IN ('SELECT','INSERT','UPDATE','DELETE')
       AND TABLE_NAME IN (
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
    IF v_total <> 288 THEN
        RAISE_APPLICATION_ERROR(-20313,
            'Se esperaban 288 permisos de objeto y existen ' || v_total || '.');
    END IF;

    SELECT COUNT(*) INTO v_total
      FROM USER_TAB_COLUMNS
     WHERE TABLE_NAME = 'TBL_ARCHIVO_EVIDENCIA_NC'
       AND COLUMN_NAME = 'CONTENIDO'
       AND DATA_TYPE = 'BLOB';
    IF v_total <> 1 THEN
        RAISE_APPLICATION_ERROR(-20314, 'El contenido de evidencias no quedó como BLOB.');
    END IF;

    DBMS_OUTPUT.PUT_LINE('OK: 24 tablas, 44 FK, 22 identidades, 40 indices, 11 triggers, 56 migraciones base y 288 permisos validados.');
END;
/

SELECT TABLE_NAME, NUM_ROWS
  FROM USER_TABLES
 WHERE TABLE_NAME LIKE 'TBL\_%\_NC' ESCAPE '\'
 ORDER BY TABLE_NAME;

SELECT OBJECT_NAME, OBJECT_TYPE, STATUS
  FROM USER_OBJECTS
 WHERE OBJECT_NAME LIKE 'TRG\_%\_NC' ESCAPE '\'
 ORDER BY OBJECT_NAME;
