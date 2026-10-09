PROMPT [8/9] Prueba transaccional de las 24 tablas

DECLARE
    v_usuario_id       NUMBER(19);
    v_proceso_id       NUMBER(19);
    v_subproceso_id    NUMBER(19);
    v_hallazgo_id      NUMBER(19);
    v_ciclo_id         NUMBER(19);
    v_actividad_id     NUMBER(19);
    v_evaluacion_id    NUMBER(19);
    v_evidencia_id     NUMBER(19);
    v_tipo_id          NUMBER(19);
    v_fuente_id        NUMBER(19);
    v_urgencia_id      NUMBER(19);
    v_prioridad_id     NUMBER(19);
    v_blob             BLOB;
    v_total            PLS_INTEGER;
BEGIN
    SAVEPOINT prueba_humo_nc;

    INSERT INTO tbl_usuario_nc (
        password, username, first_name, last_name, email,
        is_superuser, is_staff, is_active, roles
    ) VALUES (
        'pbkdf2_sha256$prueba_no_productiva', '__PRUEBA_DDL_NC__',
        'Prueba', 'DDL', 'prueba.ddl@invalid.local', 0, 0, 1,
        TO_NCLOB('["USUARIO"]')
    ) RETURNING id INTO v_usuario_id;

    SELECT COUNT(*) INTO v_total
      FROM tbl_usuario_rol_nc
     WHERE usuario_id = v_usuario_id AND rol = 'USUARIO';
    IF v_total <> 1 THEN
        RAISE_APPLICATION_ERROR(-20201, 'Fallo sincronizacion usuario/rol.');
    END IF;

    INSERT INTO tbl_proceso_nc (
        nombre, activo, gerencia, responsable_id, validadores_ids
    ) VALUES (
        '__PROCESO_PRUEBA_DDL__', 1, 'PRUEBA', v_usuario_id,
        TO_NCLOB('[' || TO_CHAR(v_usuario_id) || ']')
    ) RETURNING id INTO v_proceso_id;

    SELECT COUNT(*) INTO v_total
      FROM tbl_proceso_validador_nc
     WHERE proceso_id = v_proceso_id AND usuario_id = v_usuario_id;
    IF v_total <> 1 THEN
        RAISE_APPLICATION_ERROR(-20202, 'Fallo sincronizacion proceso/validador.');
    END IF;

    INSERT INTO tbl_subproceso_nc (proceso_id, nombre, activo)
    VALUES (v_proceso_id, '__SUBPROCESO_PRUEBA__', 1)
    RETURNING id INTO v_subproceso_id;

    SELECT id INTO v_tipo_id FROM tbl_catalogo_nc
     WHERE clase = 'TIPO' AND codigo = 'INC';
    SELECT id INTO v_fuente_id FROM tbl_catalogo_nc
     WHERE clase = 'FUENTE' AND codigo = 'OPERACION';
    SELECT id INTO v_urgencia_id FROM tbl_catalogo_nc
     WHERE clase = 'URGENCIA' AND codigo = '1';
    SELECT id INTO v_prioridad_id FROM tbl_catalogo_nc
     WHERE clase = 'PRIORIDAD' AND codigo = 'BAJA';

    INSERT INTO tbl_registro_general_nc (
        codigo, titulo, descripcion, fecha_registro, aplica_impacto,
        origen_tecnologico, version, updated_at, estado, proceso_id,
        registrado_por_id, responsable_id, subproceso_id, updated_by_id,
        tipo_registro_id, fuente_deteccion_id, urgencia_id, prioridad_id,
        es_critica
    ) VALUES (
        'SAC-TEST-2099-0001', 'Prueba de instalación Oracle',
        TO_NCLOB('Registro temporal que debe revertirse.'), LOCALTIMESTAMP,
        1, 0, 1, LOCALTIMESTAMP, 'ACCION_INMEDIATA', v_proceso_id,
        v_usuario_id, v_usuario_id, v_subproceso_id, v_usuario_id,
        v_tipo_id, v_fuente_id, v_urgencia_id, v_prioridad_id, 'NO'
    ) RETURNING id INTO v_hallazgo_id;

    INSERT INTO tbl_ciclo_tratamiento_nc (
        hallazgo_id, numero, motivo, creado_por_id, checklist_snapshot,
        respuestas, control
    ) VALUES (
        v_hallazgo_id, 1, TO_NCLOB('Ciclo de prueba'), v_usuario_id,
        TO_NCLOB('[]'), TO_NCLOB('[]'), TO_NCLOB('{}')
    ) RETURNING id INTO v_ciclo_id;

    INSERT INTO tbl_actividad_nc (
        codigo, tipo, descripcion, fecha_inicio, fet_inicial,
        fecha_vigente, estado, porcentaje_avance, resultado_esperado,
        responsable_id, ciclo_id
    ) VALUES (
        'SAC-TEST-2099-0001-A01', 'INMEDIATA',
        TO_NCLOB('Actividad de prueba'), TRUNC(SYSDATE), TRUNC(SYSDATE),
        TRUNC(SYSDATE), 'PENDIENTE', 0, TO_NCLOB('Resultado de prueba'),
        v_usuario_id, v_ciclo_id
    ) RETURNING id INTO v_actividad_id;

    INSERT INTO tbl_pbi_nc (
        ciclo_id, numero_pbi, sistema, responsable_ti_id, estado
    ) VALUES (
        v_ciclo_id, 'PBI-TEST-2099', 'Sistema de prueba', v_usuario_id, 'ABIERTO'
    );

    INSERT INTO tbl_evaluacion_eficacia_nc (
        ciclo_id, evaluador_id, fecha_evaluacion, resultado, comentario
    ) VALUES (
        v_ciclo_id, v_usuario_id, TRUNC(SYSDATE), 'EFICAZ',
        TO_NCLOB('Evaluación temporal')
    ) RETURNING id INTO v_evaluacion_id;

    INSERT INTO tbl_comunicacion_nc (
        ciclo_id, registrado_por_id, destinatarios, medio, descripcion
    ) VALUES (
        v_ciclo_id, v_usuario_id, 'Equipo de prueba', 'Portal',
        TO_NCLOB('Comunicación temporal')
    );

    INSERT INTO tbl_evidencia_nc (
        hallazgo_id, accion_id, archivo, nombre_original, mime_type,
        tamanio, subido_por_id, descripcion
    ) VALUES (
        v_hallazgo_id, v_actividad_id, 'prueba/archivo.bin', 'archivo.bin',
        'application/octet-stream', 1, v_usuario_id, TO_NCLOB('Evidencia temporal')
    ) RETURNING id INTO v_evidencia_id;

    INSERT INTO tbl_archivo_evidencia_nc (
        contenido, sha256, evidencia_id
    ) VALUES (
        EMPTY_BLOB(),
        '6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d',
        v_evidencia_id
    ) RETURNING contenido INTO v_blob;
    DBMS_LOB.WRITEAPPEND(v_blob, 1, HEXTORAW('00'));

    SELECT DBMS_LOB.GETLENGTH(contenido) INTO v_total
      FROM tbl_archivo_evidencia_nc
     WHERE evidencia_id = v_evidencia_id;
    IF v_total <> 1 THEN
        RAISE_APPLICATION_ERROR(-20203, 'Fallo escritura/lectura BLOB.');
    END IF;

    INSERT INTO tbl_historial_hallazgo_nc (
        accion_relacionada_id, hallazgo_id, usuario_id, accion,
        estado_anterior, estado_nuevo, comentario, metadata_json
    ) VALUES (
        v_actividad_id, v_hallazgo_id, v_usuario_id, 'PRUEBA_INSTALACION',
        'BORRADOR', 'ACCION_INMEDIATA', TO_NCLOB('Evento temporal'), TO_NCLOB('{}')
    );

    INSERT INTO tbl_notificacion_nc (
        usuario_id, hallazgo_id, tipo, titulo, mensaje, leida
    ) VALUES (
        v_usuario_id, v_hallazgo_id, 'PRUEBA', 'Prueba de instalación',
        TO_NCLOB('Notificación temporal'), 0
    );

    INSERT INTO tbl_auditoria_administracion_nc (
        usuario_id, entidad, objeto, accion, antes, despues
    ) VALUES (
        v_usuario_id, 'INSTALACION', 'PRUEBA', 'VALIDAR',
        TO_NCLOB('{}'), TO_NCLOB('{"resultado":"OK"}')
    );

    INSERT INTO tbl_correlativo_sac_nc (anio, ambito, ultimo_numero)
    VALUES (2099, 'TEST', 1);

    INSERT INTO tbl_django_migrations_nc (app, name, applied)
    VALUES ('prueba_nc', '0001_prueba', LOCALTIMESTAMP);

    INSERT INTO tbl_django_session_nc (session_key, session_data, expire_date)
    VALUES ('0000000000000000000000000000000000000000', 'prueba',
            LOCALTIMESTAMP + INTERVAL '1' HOUR);

    SELECT COUNT(*) INTO v_total FROM tbl_matriz_prioridad_nc;
    IF v_total <> 9 THEN
        RAISE_APPLICATION_ERROR(-20204, 'La matriz de prioridad no contiene 9 combinaciones.');
    END IF;

    SELECT COUNT(*) INTO v_total FROM tbl_pregunta_causa_nc;
    IF v_total <> 32 THEN
        RAISE_APPLICATION_ERROR(-20205, 'La matriz 6M no contiene 32 preguntas.');
    END IF;

    ROLLBACK TO prueba_humo_nc;
    DBMS_OUTPUT.PUT_LINE('OK: prueba de las 24 tablas, relaciones, JSON, BLOB e identidades revertida.');
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK TO prueba_humo_nc;
        RAISE;
END;
/

COMMIT;
