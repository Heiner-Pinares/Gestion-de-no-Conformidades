-- ============================================================================
-- PORTAL CLARO - GESTION DE NO CONFORMIDADES
-- INSTALADOR ORACLE 19c TODO EN UNO
-- Esquema propietario: USRFACT
-- Usuarios con acceso: C27826, C28111 y C28134
--
-- Ejecutar el archivo completo conectado como USRFACT en una ventana de
-- comandos de PL/SQL Developer. No requiere archivos SQL adicionales.
-- Uso exclusivo sobre un esquema nuevo donde no existan tablas del Portal NC.
-- Oracle confirma cada DDL de forma implicita; un ROLLBACK no elimina objetos
-- que hayan sido creados antes de un error. Ejecutar primero en homologacion.
--
-- Los campos JSON usan NCLOB intencionalmente porque es el tipo de JSONField
-- del backend Oracle de Django 5.2. La prevalidacion lo prueba antes del DDL
-- definitivo. Las 56 filas de migraciones coinciden con el codigo entregado.
-- ============================================================================

SET DEFINE OFF
SET SERVEROUTPUT ON SIZE UNLIMITED
SET ECHO ON
SET FEEDBACK ON
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK

ALTER SESSION SET TIME_ZONE = 'UTC';

PROMPT ============================================================
PROMPT Portal NC - instalacion completa y autocontenida en USRFACT
PROMPT ============================================================


-- ============================================================================
-- INICIO DEL MODULO INTEGRADO: 00_prevalidacion.sql
-- ============================================================================
PROMPT [0/9] Prevalidacion de Oracle y del esquema

DECLARE
    v_existentes        PLS_INTEGER;
    v_objetos           PLS_INTEGER;
    v_restricciones     PLS_INTEGER;
    v_usuarios          PLS_INTEGER;
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

    -- Prueba efectiva de las capacidades requeridas. Verifica antes de crear
    -- las tablas definitivas: CREATE TABLE, cuota, nombres de más de 30 bytes
    -- (COMPATIBLE >= 12.2), CREATE TRIGGER y el tipo exacto que Django 5.2
    -- usa para JSONField en Oracle: NCLOB con restricción IS JSON.
    -- Los objetos temporales se eliminan inmediatamente.
    BEGIN
        EXECUTE IMMEDIATE q'[CREATE TABLE tbl_nc_prevalidacion_nombre_largo_123 (
            id NUMBER,
            datos NCLOB,
            CONSTRAINT ck_nc_prevalidacion_json_123
                CHECK (datos IS JSON (STRICT))
        )]';
        EXECUTE IMMEDIATE q'[INSERT INTO tbl_nc_prevalidacion_nombre_largo_123
            (id, datos) VALUES (1, TO_NCLOB('{"portal":"nc"}'))]';
        EXECUTE IMMEDIATE q'[SELECT COUNT(*)
            FROM tbl_nc_prevalidacion_nombre_largo_123
            WHERE datos IS JSON (STRICT)]' INTO v_json;
        IF v_json <> 1 THEN
            RAISE_APPLICATION_ERROR(-20007,
                'La prueba NCLOB con IS JSON no devolvio el registro esperado.');
        END IF;
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
                'USRFACT no supera la prevalidacion DDL/JSON. Revise CREATE TABLE, CREATE TRIGGER, cuota, COMPATIBLE >= 12.2 y NCLOB IS JSON. Detalle: ' || SQLERRM);
    END;

    DBMS_OUTPUT.PUT_LINE('OK: usuario=' || USER ||
                         ', Oracle=' || DBMS_DB_VERSION.VERSION || '.' || DBMS_DB_VERSION.RELEASE ||
                         ', usuarios destino=3, tablas previas=0, DDL y NCLOB IS JSON verificados.');
END;
/
-- FIN DEL MODULO INTEGRADO: 00_prevalidacion.sql

-- ============================================================================
-- INICIO DEL MODULO INTEGRADO: 01_crear_tablas.sql
-- ============================================================================
PROMPT [1/9] Creacion de 24 tablas, PK, UK y CHECK

CREATE TABLE tbl_usuario_nc (
    id                    NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                              (START WITH 1 INCREMENT BY 1 CACHE 100),
    password              NVARCHAR2(128) NOT NULL,
    last_login            TIMESTAMP(6),
    is_superuser          NUMBER(1) DEFAULT 0 NOT NULL,
    username              NVARCHAR2(150) NOT NULL,
    first_name            NVARCHAR2(150),
    last_name             NVARCHAR2(150),
    email                 NVARCHAR2(254),
    is_staff              NUMBER(1) DEFAULT 0 NOT NULL,
    is_active             NUMBER(1) DEFAULT 1 NOT NULL,
    date_joined           TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    area                  NVARCHAR2(150),
    cargo                 NVARCHAR2(150),
    corporate_identifier  NVARCHAR2(255),
    roles                 NCLOB NOT NULL,
    direccion             NVARCHAR2(150),
    gerencia              NVARCHAR2(150),
    jefe_id               NUMBER(19),
    CONSTRAINT pk_usuario_nc PRIMARY KEY (id),
    CONSTRAINT uk_usuario_username_nc UNIQUE (username),
    CONSTRAINT uk_usuario_corp_nc UNIQUE (corporate_identifier),
    CONSTRAINT ck_usr_super_nc CHECK (is_superuser IN (0, 1)),
    CONSTRAINT ck_usr_staff_nc CHECK (is_staff IN (0, 1)),
    CONSTRAINT ck_usr_active_nc CHECK (is_active IN (0, 1)),
    CONSTRAINT ck_usr_roles_json_nc CHECK (roles IS JSON (STRICT))
);

CREATE TABLE tbl_usuario_rol_nc (
    id          NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                    (START WITH 1 INCREMENT BY 1 CACHE 100),
    rol         NVARCHAR2(20) NOT NULL,
    usuario_id  NUMBER(19) NOT NULL,
    CONSTRAINT pk_usuario_rol_nc PRIMARY KEY (id),
    CONSTRAINT uk_usuario_rol_nc UNIQUE (usuario_id, rol),
    CONSTRAINT ck_usuario_rol_nc CHECK
        (rol IN ('USUARIO', 'VALIDADOR', 'ADMINISTRADOR'))
);

CREATE TABLE tbl_catalogo_nc (
    id      NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                (START WITH 1 INCREMENT BY 1 CACHE 100),
    clase   NVARCHAR2(12) NOT NULL,
    codigo  NVARCHAR2(30) NOT NULL,
    nombre  NVARCHAR2(180) NOT NULL,
    activo  NUMBER(1) DEFAULT 1 NOT NULL,
    valor   NUMBER(5),
    orden   NUMBER(5) DEFAULT 0 NOT NULL,
    CONSTRAINT pk_catalogo_nc PRIMARY KEY (id),
    CONSTRAINT uk_cat_clase_codigo_nc UNIQUE (clase, codigo),
    CONSTRAINT uk_cat_clase_valor_nc UNIQUE (clase, valor),
    CONSTRAINT ck_cat_clase_nc CHECK
        (clase IN ('TIPO','FUENTE','IMPACTO','URGENCIA','PRIORIDAD','CATEGORIA')),
    CONSTRAINT ck_cat_activo_nc CHECK (activo IN (0, 1)),
    CONSTRAINT ck_cat_valor_nc CHECK (valor IS NULL OR valor >= 0),
    CONSTRAINT ck_cat_orden_nc CHECK (orden >= 0)
);

CREATE TABLE tbl_proceso_nc (
    id               NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                         (START WITH 1 INCREMENT BY 1 CACHE 100),
    nombre           NVARCHAR2(180) NOT NULL,
    activo           NUMBER(1) DEFAULT 1 NOT NULL,
    gerencia         NVARCHAR2(180),
    responsable_id   NUMBER(19),
    validadores_ids  NCLOB NOT NULL,
    CONSTRAINT pk_proceso_nc PRIMARY KEY (id),
    CONSTRAINT uk_proceso_nombre_nc UNIQUE (nombre),
    CONSTRAINT ck_proceso_activo_nc CHECK (activo IN (0, 1)),
    CONSTRAINT ck_proceso_json_nc CHECK (validadores_ids IS JSON (STRICT))
);

CREATE TABLE tbl_proceso_validador_nc (
    id          NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                    (START WITH 1 INCREMENT BY 1 CACHE 100),
    proceso_id  NUMBER(19) NOT NULL,
    usuario_id  NUMBER(19) NOT NULL,
    CONSTRAINT pk_proceso_validador_nc PRIMARY KEY (id),
    CONSTRAINT uk_proceso_validador_nc UNIQUE (proceso_id, usuario_id)
);

CREATE TABLE tbl_subproceso_nc (
    id          NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                    (START WITH 1 INCREMENT BY 1 CACHE 100),
    proceso_id  NUMBER(19) NOT NULL,
    nombre      NVARCHAR2(180) NOT NULL,
    activo      NUMBER(1) DEFAULT 1 NOT NULL,
    CONSTRAINT pk_subproceso_nc PRIMARY KEY (id),
    CONSTRAINT uk_subproceso_nombre_nc UNIQUE (proceso_id, nombre),
    CONSTRAINT ck_subproceso_activo_nc CHECK (activo IN (0, 1))
);

CREATE TABLE tbl_matriz_prioridad_nc (
    id            NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                      (START WITH 1 INCREMENT BY 1 CACHE 100),
    impacto_id    NUMBER(19) NOT NULL,
    urgencia_id   NUMBER(19) NOT NULL,
    prioridad_id  NUMBER(19) NOT NULL,
    activo        NUMBER(1) DEFAULT 1 NOT NULL,
    es_demo       NUMBER(1) DEFAULT 1 NOT NULL,
    CONSTRAINT pk_matriz_prioridad_nc PRIMARY KEY (id),
    CONSTRAINT uk_matriz_imp_urg_nc UNIQUE (impacto_id, urgencia_id),
    CONSTRAINT ck_matriz_activo_nc CHECK (activo IN (0, 1)),
    CONSTRAINT ck_matriz_demo_nc CHECK (es_demo IN (0, 1))
);

CREATE TABLE tbl_configuracion_impacto_nc (
    id                       NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                                 (START WITH 1 INCREMENT BY 1 CACHE 100),
    predeterminada           NUMBER(1) DEFAULT 1 NOT NULL,
    clientes_bajo_desde      NUMBER(19) DEFAULT 0 NOT NULL,
    clientes_bajo_hasta      NUMBER(19) DEFAULT 90 NOT NULL,
    clientes_medio_desde     NUMBER(19) DEFAULT 91 NOT NULL,
    clientes_medio_hasta     NUMBER(19) DEFAULT 499 NOT NULL,
    clientes_alto_desde      NUMBER(19) DEFAULT 500 NOT NULL,
    tiempo_bajo_desde        NUMBER(10) DEFAULT 0 NOT NULL,
    tiempo_bajo_hasta        NUMBER(10) DEFAULT 29 NOT NULL,
    tiempo_medio_desde       NUMBER(10) DEFAULT 30 NOT NULL,
    tiempo_medio_hasta       NUMBER(10) DEFAULT 120 NOT NULL,
    tiempo_alto_desde        NUMBER(10) DEFAULT 121 NOT NULL,
    financiero_bajo_desde    NUMBER(14,0) DEFAULT 0 NOT NULL,
    financiero_bajo_hasta    NUMBER(14,0) DEFAULT 999999 NOT NULL,
    financiero_medio_desde   NUMBER(14,0) DEFAULT 1000000 NOT NULL,
    financiero_medio_hasta   NUMBER(14,0) DEFAULT 1999999 NOT NULL,
    financiero_alto_desde    NUMBER(14,0) DEFAULT 2000000 NOT NULL,
    CONSTRAINT pk_conf_impacto_nc PRIMARY KEY (id),
    CONSTRAINT ck_conf_imp_pred_nc CHECK (predeterminada IN (0, 1)),
    CONSTRAINT ck_conf_imp_clientes_nc CHECK (
        clientes_bajo_desde >= 0 AND
        clientes_bajo_desde <= clientes_bajo_hasta AND
        clientes_bajo_hasta < clientes_medio_desde AND
        clientes_medio_desde <= clientes_medio_hasta AND
        clientes_medio_hasta < clientes_alto_desde),
    CONSTRAINT ck_conf_imp_tiempo_nc CHECK (
        tiempo_bajo_desde >= 0 AND
        tiempo_bajo_desde <= tiempo_bajo_hasta AND
        tiempo_bajo_hasta < tiempo_medio_desde AND
        tiempo_medio_desde <= tiempo_medio_hasta AND
        tiempo_medio_hasta < tiempo_alto_desde),
    CONSTRAINT ck_conf_imp_fin_nc CHECK (
        financiero_bajo_desde >= 0 AND
        financiero_bajo_desde <= financiero_bajo_hasta AND
        financiero_bajo_hasta < financiero_medio_desde AND
        financiero_medio_desde <= financiero_medio_hasta AND
        financiero_medio_hasta < financiero_alto_desde)
);

CREATE TABLE tbl_configuracion_urgencia_nc (
    id                    NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                              (START WITH 1 INCREMENT BY 1 CACHE 100),
    codigo                NVARCHAR2(30) NOT NULL,
    nombre                NVARCHAR2(180) NOT NULL,
    activo                NUMBER(1) DEFAULT 1 NOT NULL,
    tiempo_bajo_desde     NUMBER(10) DEFAULT 0 NOT NULL,
    tiempo_bajo_hasta     NUMBER(10) DEFAULT 27 NOT NULL,
    tiempo_medio_desde    NUMBER(10) DEFAULT 28 NOT NULL,
    tiempo_medio_hasta    NUMBER(10) DEFAULT 32 NOT NULL,
    tiempo_alto_desde     NUMBER(10) DEFAULT 33 NOT NULL,
    CONSTRAINT pk_conf_urgencia_nc PRIMARY KEY (id),
    CONSTRAINT uk_conf_urg_codigo_nc UNIQUE (codigo),
    CONSTRAINT ck_conf_urg_codigo_nc CHECK
        (codigo IN ('FACTURACION', 'POST_FACTURACION')),
    CONSTRAINT ck_conf_urg_activo_nc CHECK (activo IN (0, 1)),
    CONSTRAINT ck_conf_urg_rangos_nc CHECK (
        tiempo_bajo_desde >= 0 AND
        tiempo_bajo_desde <= tiempo_bajo_hasta AND
        tiempo_bajo_hasta < tiempo_medio_desde AND
        tiempo_medio_desde <= tiempo_medio_hasta AND
        tiempo_medio_hasta < tiempo_alto_desde)
);

CREATE TABLE tbl_pregunta_causa_nc (
    codigo        NVARCHAR2(30) NOT NULL,
    categoria_id  NUMBER(19) NOT NULL,
    texto         NCLOB NOT NULL,
    orden         NUMBER(5) NOT NULL,
    activo        NUMBER(1) DEFAULT 1 NOT NULL,
    CONSTRAINT pk_pregunta_causa_nc PRIMARY KEY (codigo),
    CONSTRAINT ck_pregunta_orden_nc CHECK (orden >= 0),
    CONSTRAINT ck_pregunta_activo_nc CHECK (activo IN (0, 1))
);

CREATE TABLE tbl_auditoria_administracion_nc (
    id          NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                    (START WITH 1 INCREMENT BY 1 CACHE 100),
    usuario_id  NUMBER(19) NOT NULL,
    fecha       TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    entidad     NVARCHAR2(100) NOT NULL,
    objeto      NVARCHAR2(100) NOT NULL,
    accion      NVARCHAR2(70) NOT NULL,
    antes       NCLOB NOT NULL,
    despues     NCLOB NOT NULL,
    CONSTRAINT pk_auditoria_admin_nc PRIMARY KEY (id),
    CONSTRAINT ck_auditoria_antes_nc CHECK (antes IS JSON (STRICT)),
    CONSTRAINT ck_auditoria_desp_nc CHECK (despues IS JSON (STRICT))
);

CREATE TABLE tbl_correlativo_sac_nc (
    id             NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                       (START WITH 1 INCREMENT BY 1 CACHE 100),
    anio           NUMBER(5) NOT NULL,
    ambito         NVARCHAR2(10) NOT NULL,
    ultimo_numero  NUMBER(10) DEFAULT 0 NOT NULL,
    CONSTRAINT pk_correlativo_sac_nc PRIMARY KEY (id),
    CONSTRAINT uk_correlativo_sac_nc UNIQUE (anio, ambito),
    CONSTRAINT ck_correlativo_anio_nc CHECK (anio >= 2000),
    CONSTRAINT ck_correlativo_num_nc CHECK (ultimo_numero >= 0)
);

CREATE TABLE tbl_registro_general_nc (
    id                              NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                                        (START WITH 1 INCREMENT BY 1 CACHE 100),
    codigo                          NVARCHAR2(40) NOT NULL,
    titulo                          NVARCHAR2(250) NOT NULL,
    descripcion                     NCLOB,
    ticket_remedy                   NVARCHAR2(120),
    fecha_deteccion                 TIMESTAMP(6),
    fecha_registro                  TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    fecha_solucion                  DATE,
    impacto_clientes                NUMBER(5),
    impacto_tiempo                  NUMBER(5),
    impacto_soles                   NUMBER(5),
    impacto_resultante              NUMBER(5),
    prioridad_snapshot              NVARCHAR2(180),
    aplica_impacto                  NUMBER(1) DEFAULT 1 NOT NULL,
    justificacion_no_impacto        NCLOB,
    es_critica                      NVARCHAR2(2),
    origen_tecnologico              NUMBER(1) DEFAULT 0 NOT NULL,
    criterio_categoria              NCLOB,
    requisito_referencia            NCLOB,
    version                         NUMBER(10) DEFAULT 1 NOT NULL,
    updated_at                      TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    estado                          NVARCHAR2(30) DEFAULT 'BORRADOR' NOT NULL,
    proceso_id                      NUMBER(19) NOT NULL,
    registrado_por_id               NUMBER(19) NOT NULL,
    responsable_id                  NUMBER(19) NOT NULL,
    subproceso_id                   NUMBER(19),
    updated_by_id                   NUMBER(19),
    tipo_registro_id                NUMBER(19) NOT NULL,
    fuente_deteccion_id             NUMBER(19),
    urgencia_id                     NUMBER(19),
    prioridad_id                    NUMBER(19),
    actividad                       NVARCHAR2(250),
    impacto_clientes_seleccion      NVARCHAR2(180),
    impacto_financiero_seleccion    NVARCHAR2(180),
    impacto_tiempo_seleccion        NVARCHAR2(180),
    urgencia_area                   NVARCHAR2(80),
    urgencia_seleccion              NVARCHAR2(180),
    CONSTRAINT pk_registro_general_nc PRIMARY KEY (id),
    CONSTRAINT uk_registro_codigo_nc UNIQUE (codigo),
    CONSTRAINT ck_reg_aplica_imp_nc CHECK (aplica_impacto IN (0, 1)),
    CONSTRAINT ck_reg_origen_tec_nc CHECK (origen_tecnologico IN (0, 1)),
    CONSTRAINT ck_reg_version_nc CHECK (version >= 0),
    CONSTRAINT ck_reg_imp_clientes_nc CHECK
        (impacto_clientes IS NULL OR impacto_clientes BETWEEN 1 AND 3),
    CONSTRAINT ck_reg_imp_tiempo_nc CHECK
        (impacto_tiempo IS NULL OR impacto_tiempo BETWEEN 1 AND 3),
    CONSTRAINT ck_reg_imp_soles_nc CHECK
        (impacto_soles IS NULL OR impacto_soles BETWEEN 1 AND 3),
    CONSTRAINT ck_reg_imp_result_nc CHECK
        (impacto_resultante IS NULL OR impacto_resultante BETWEEN 1 AND 3),
    CONSTRAINT ck_reg_critica_nc CHECK
        (es_critica IS NULL OR es_critica IN ('SI', 'NO', 'NA'))
);

CREATE TABLE tbl_ciclo_tratamiento_nc (
    id                       NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                                 (START WITH 1 INCREMENT BY 1 CACHE 100),
    hallazgo_id              NUMBER(19) NOT NULL,
    numero                   NUMBER(10) NOT NULL,
    motivo                   NCLOB NOT NULL,
    creado_por_id            NUMBER(19) NOT NULL,
    fecha_inicio             TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    fecha_fin                TIMESTAMP(6),
    analisis_responsable_id  NUMBER(19),
    analisis_inicio          TIMESTAMP(6),
    analisis_fin             TIMESTAMP(6),
    causa_raiz               NCLOB,
    checklist_snapshot       NCLOB NOT NULL,
    respuestas               NCLOB NOT NULL,
    control                  NCLOB NOT NULL,
    responsable_cierre_id    NUMBER(19),
    fecha_cierre             TIMESTAMP(6),
    comentarios_cierre       NCLOB,
    resultado_cierre         NVARCHAR2(12),
    CONSTRAINT pk_ciclo_tratamiento_nc PRIMARY KEY (id),
    CONSTRAINT uk_ciclo_hallazgo_nc UNIQUE (hallazgo_id, numero),
    CONSTRAINT ck_ciclo_numero_nc CHECK (numero >= 0),
    CONSTRAINT ck_ciclo_check_json_nc CHECK (checklist_snapshot IS JSON (STRICT)),
    CONSTRAINT ck_ciclo_resp_json_nc CHECK (respuestas IS JSON (STRICT)),
    CONSTRAINT ck_ciclo_ctrl_json_nc CHECK (control IS JSON (STRICT)),
    CONSTRAINT ck_ciclo_resultado_nc CHECK
        (resultado_cierre IS NULL OR resultado_cierre IN ('EFICAZ', 'NO_EFICAZ'))
);

CREATE TABLE tbl_actividad_nc (
    id                  NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                            (START WITH 1 INCREMENT BY 1 CACHE 100),
    codigo              NVARCHAR2(50) NOT NULL,
    tipo                NVARCHAR2(18) NOT NULL,
    descripcion         NCLOB NOT NULL,
    fecha_inicio        DATE NOT NULL,
    fet_inicial         DATE,
    fecha_vigente       DATE,
    fecha_real          DATE,
    estado              NVARCHAR2(12) DEFAULT 'PENDIENTE' NOT NULL,
    porcentaje_avance   NUMBER(5) DEFAULT 0 NOT NULL,
    resultado_esperado  NCLOB NOT NULL,
    comentario          NCLOB,
    created_at          TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    updated_at          TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    responsable_id      NUMBER(19),
    ciclo_id            NUMBER(19) NOT NULL,
    CONSTRAINT pk_actividad_nc PRIMARY KEY (id),
    CONSTRAINT uk_actividad_codigo_nc UNIQUE (codigo),
    CONSTRAINT ck_actividad_avance_nc CHECK (porcentaje_avance BETWEEN 0 AND 100),
    CONSTRAINT ck_actividad_tipo_nc CHECK
        (tipo IN ('INMEDIATA', 'ACCION_INMEDIATA', 'CORRECTIVA')),
    CONSTRAINT ck_actividad_estado_nc CHECK
        (estado IN ('PENDIENTE', 'EN_PROCESO', 'COMPLETADA', 'CANCELADA')),
    CONSTRAINT ck_actividad_fet_nc CHECK
        (fet_inicial IS NULL OR fet_inicial >= fecha_inicio),
    CONSTRAINT ck_actividad_vigente_nc CHECK
        (fecha_vigente IS NULL OR fecha_vigente >= fecha_inicio),
    CONSTRAINT ck_actividad_real_nc CHECK
        (fecha_real IS NULL OR fecha_real >= fecha_inicio),
    CONSTRAINT ck_actividad_completa_nc CHECK (
        (estado = 'COMPLETADA' AND porcentaje_avance = 100 AND fecha_real IS NOT NULL)
        OR
        (estado <> 'COMPLETADA' AND porcentaje_avance < 100 AND fecha_real IS NULL)
    )
);

CREATE TABLE tbl_pbi_nc (
    id                 NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                           (START WITH 1 INCREMENT BY 1 CACHE 100),
    ciclo_id           NUMBER(19) NOT NULL,
    numero_pbi         NVARCHAR2(100) NOT NULL,
    ticket_incidente   NVARCHAR2(100),
    sistema            NVARCHAR2(200) NOT NULL,
    herramienta        NVARCHAR2(100) DEFAULT 'Helix (registro manual)' NOT NULL,
    responsable_ti_id  NUMBER(19) NOT NULL,
    estado             NVARCHAR2(10) DEFAULT 'ABIERTO' NOT NULL,
    fecha_creacion     TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    fecha_cierre_pbi   DATE,
    observacion        NCLOB,
    CONSTRAINT pk_pbi_nc PRIMARY KEY (id),
    CONSTRAINT uk_pbi_ciclo_numero_nc UNIQUE (ciclo_id, numero_pbi),
    CONSTRAINT ck_pbi_estado_nc CHECK (estado IN ('ABIERTO', 'CERRADO')),
    CONSTRAINT ck_pbi_cierre_nc CHECK (
        (estado = 'ABIERTO' AND fecha_cierre_pbi IS NULL)
        OR
        (estado = 'CERRADO' AND fecha_cierre_pbi IS NOT NULL)
    )
);

CREATE TABLE tbl_evaluacion_eficacia_nc (
    id                NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                          (START WITH 1 INCREMENT BY 1 CACHE 100),
    ciclo_id          NUMBER(19) NOT NULL,
    evaluador_id      NUMBER(19) NOT NULL,
    fecha_evaluacion  DATE NOT NULL,
    resultado         NVARCHAR2(12) NOT NULL,
    comentario        NCLOB NOT NULL,
    fecha_registro    TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    CONSTRAINT pk_evaluacion_eficacia_nc PRIMARY KEY (id),
    CONSTRAINT ck_eval_resultado_nc CHECK
        (resultado IN ('EFICAZ', 'NO_EFICAZ'))
);

CREATE TABLE tbl_comunicacion_nc (
    id                 NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                           (START WITH 1 INCREMENT BY 1 CACHE 100),
    ciclo_id           NUMBER(19) NOT NULL,
    registrado_por_id  NUMBER(19) NOT NULL,
    destinatarios      NVARCHAR2(500) NOT NULL,
    medio              NVARCHAR2(120) NOT NULL,
    descripcion        NCLOB NOT NULL,
    fecha              TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    CONSTRAINT pk_comunicacion_nc PRIMARY KEY (id)
);

CREATE TABLE tbl_evidencia_nc (
    id               NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                         (START WITH 1 INCREMENT BY 1 CACHE 100),
    hallazgo_id      NUMBER(19) NOT NULL,
    accion_id        NUMBER(19),
    analisis_id      NUMBER(19),
    evaluacion_id    NUMBER(19),
    cierre_id        NUMBER(19),
    archivo          NVARCHAR2(100) NOT NULL,
    nombre_original  NVARCHAR2(255) NOT NULL,
    mime_type        NVARCHAR2(100) NOT NULL,
    tamanio          NUMBER(10) NOT NULL,
    subido_por_id    NUMBER(19) NOT NULL,
    fecha_carga      TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    descripcion      NCLOB,
    CONSTRAINT pk_evidencia_nc PRIMARY KEY (id),
    CONSTRAINT ck_evidencia_tamanio_nc CHECK (tamanio > 0),
    CONSTRAINT ck_evidencia_contexto_nc CHECK (
        (CASE WHEN accion_id IS NULL THEN 0 ELSE 1 END) +
        (CASE WHEN analisis_id IS NULL THEN 0 ELSE 1 END) +
        (CASE WHEN evaluacion_id IS NULL THEN 0 ELSE 1 END) +
        (CASE WHEN cierre_id IS NULL THEN 0 ELSE 1 END) <= 1
    )
);

CREATE TABLE tbl_archivo_evidencia_nc (
    id            NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                      (START WITH 1 INCREMENT BY 1 CACHE 100),
    contenido     BLOB NOT NULL,
    sha256        NVARCHAR2(64) NOT NULL,
    evidencia_id  NUMBER(19) NOT NULL,
    CONSTRAINT pk_archivo_evidencia_nc PRIMARY KEY (id),
    CONSTRAINT uk_archivo_evidencia_nc UNIQUE (evidencia_id),
    CONSTRAINT ck_archivo_sha256_nc CHECK
        (REGEXP_LIKE(sha256, '^[0-9A-Fa-f]{64}$'))
);

CREATE TABLE tbl_historial_hallazgo_nc (
    id                    NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                              (START WITH 1 INCREMENT BY 1 CACHE 100),
    accion_relacionada_id  NUMBER(19),
    hallazgo_id            NUMBER(19) NOT NULL,
    usuario_id             NUMBER(19) NOT NULL,
    fecha_hora             TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    accion                 NVARCHAR2(70) NOT NULL,
    estado_anterior        NVARCHAR2(30),
    estado_nuevo           NVARCHAR2(30),
    comentario             NCLOB,
    metadata_json          NCLOB NOT NULL,
    CONSTRAINT pk_historial_hallazgo_nc PRIMARY KEY (id),
    CONSTRAINT ck_historial_json_nc CHECK (metadata_json IS JSON (STRICT))
);

CREATE TABLE tbl_notificacion_nc (
    id              NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                        (START WITH 1 INCREMENT BY 1 CACHE 100),
    usuario_id      NUMBER(19) NOT NULL,
    hallazgo_id     NUMBER(19) NOT NULL,
    tipo            NVARCHAR2(50) NOT NULL,
    titulo          NVARCHAR2(250) NOT NULL,
    mensaje         NCLOB NOT NULL,
    leida           NUMBER(1) DEFAULT 0 NOT NULL,
    fecha_creacion  TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    fecha_lectura   TIMESTAMP(6),
    CONSTRAINT pk_notificacion_nc PRIMARY KEY (id),
    CONSTRAINT ck_notificacion_leida_nc CHECK (leida IN (0, 1)),
    CONSTRAINT ck_notificacion_fecha_nc CHECK
        ((leida = 0 AND fecha_lectura IS NULL) OR leida = 1)
);

CREATE TABLE tbl_django_migrations_nc (
    id       NUMBER(19) GENERATED BY DEFAULT ON NULL AS IDENTITY
                 (START WITH 1 INCREMENT BY 1 CACHE 100),
    app      NVARCHAR2(255) NOT NULL,
    name     NVARCHAR2(255) NOT NULL,
    applied  TIMESTAMP(6) DEFAULT LOCALTIMESTAMP NOT NULL,
    CONSTRAINT pk_django_migrations_nc PRIMARY KEY (id),
    CONSTRAINT uk_django_migration_nc UNIQUE (app, name)
);

CREATE TABLE tbl_django_session_nc (
    session_key   NVARCHAR2(40) NOT NULL,
    session_data  NCLOB NOT NULL,
    expire_date   TIMESTAMP(6) NOT NULL,
    CONSTRAINT pk_django_session_nc PRIMARY KEY (session_key)
);

PROMPT OK: 24 tablas creadas.
-- FIN DEL MODULO INTEGRADO: 01_crear_tablas.sql

-- ============================================================================
-- INICIO DEL MODULO INTEGRADO: 02_relaciones_indices.sql
-- ============================================================================
PROMPT [2/9] Creacion de 44 relaciones y de indices

ALTER TABLE tbl_usuario_nc ADD CONSTRAINT fk_usr_jefe_nc
    FOREIGN KEY (jefe_id) REFERENCES tbl_usuario_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_usuario_rol_nc ADD CONSTRAINT fk_usr_rol_usuario_nc
    FOREIGN KEY (usuario_id) REFERENCES tbl_usuario_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_proceso_nc ADD CONSTRAINT fk_proceso_responsable_nc
    FOREIGN KEY (responsable_id) REFERENCES tbl_usuario_nc(id);

ALTER TABLE tbl_proceso_validador_nc ADD CONSTRAINT fk_proc_val_proceso_nc
    FOREIGN KEY (proceso_id) REFERENCES tbl_proceso_nc(id) ON DELETE CASCADE;

ALTER TABLE tbl_proceso_validador_nc ADD CONSTRAINT fk_proc_val_usuario_nc
    FOREIGN KEY (usuario_id) REFERENCES tbl_usuario_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_subproceso_nc ADD CONSTRAINT fk_subproc_proceso_nc
    FOREIGN KEY (proceso_id) REFERENCES tbl_proceso_nc(id);

ALTER TABLE tbl_matriz_prioridad_nc ADD CONSTRAINT fk_matriz_impacto_nc
    FOREIGN KEY (impacto_id) REFERENCES tbl_catalogo_nc(id);

ALTER TABLE tbl_matriz_prioridad_nc ADD CONSTRAINT fk_matriz_urgencia_nc
    FOREIGN KEY (urgencia_id) REFERENCES tbl_catalogo_nc(id);

ALTER TABLE tbl_matriz_prioridad_nc ADD CONSTRAINT fk_matriz_prioridad_nc
    FOREIGN KEY (prioridad_id) REFERENCES tbl_catalogo_nc(id);

ALTER TABLE tbl_pregunta_causa_nc ADD CONSTRAINT fk_pregunta_categoria_nc
    FOREIGN KEY (categoria_id) REFERENCES tbl_catalogo_nc(id);

ALTER TABLE tbl_auditoria_administracion_nc ADD CONSTRAINT fk_audit_usuario_nc
    FOREIGN KEY (usuario_id) REFERENCES tbl_usuario_nc(id);

ALTER TABLE tbl_registro_general_nc ADD CONSTRAINT fk_reg_proceso_nc
    FOREIGN KEY (proceso_id) REFERENCES tbl_proceso_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_registro_general_nc ADD CONSTRAINT fk_reg_registrado_nc
    FOREIGN KEY (registrado_por_id) REFERENCES tbl_usuario_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_registro_general_nc ADD CONSTRAINT fk_reg_responsable_nc
    FOREIGN KEY (responsable_id) REFERENCES tbl_usuario_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_registro_general_nc ADD CONSTRAINT fk_reg_subproceso_nc
    FOREIGN KEY (subproceso_id) REFERENCES tbl_subproceso_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_registro_general_nc ADD CONSTRAINT fk_reg_actualizado_nc
    FOREIGN KEY (updated_by_id) REFERENCES tbl_usuario_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_registro_general_nc ADD CONSTRAINT fk_reg_tipo_nc
    FOREIGN KEY (tipo_registro_id) REFERENCES tbl_catalogo_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_registro_general_nc ADD CONSTRAINT fk_reg_fuente_nc
    FOREIGN KEY (fuente_deteccion_id) REFERENCES tbl_catalogo_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_registro_general_nc ADD CONSTRAINT fk_reg_urgencia_nc
    FOREIGN KEY (urgencia_id) REFERENCES tbl_catalogo_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_registro_general_nc ADD CONSTRAINT fk_reg_prioridad_nc
    FOREIGN KEY (prioridad_id) REFERENCES tbl_catalogo_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_ciclo_tratamiento_nc ADD CONSTRAINT fk_ciclo_hallazgo_nc
    FOREIGN KEY (hallazgo_id) REFERENCES tbl_registro_general_nc(id);

ALTER TABLE tbl_ciclo_tratamiento_nc ADD CONSTRAINT fk_ciclo_creador_nc
    FOREIGN KEY (creado_por_id) REFERENCES tbl_usuario_nc(id);

ALTER TABLE tbl_ciclo_tratamiento_nc ADD CONSTRAINT fk_ciclo_analista_nc
    FOREIGN KEY (analisis_responsable_id) REFERENCES tbl_usuario_nc(id);

ALTER TABLE tbl_ciclo_tratamiento_nc ADD CONSTRAINT fk_ciclo_cierre_nc
    FOREIGN KEY (responsable_cierre_id) REFERENCES tbl_usuario_nc(id);

ALTER TABLE tbl_actividad_nc ADD CONSTRAINT fk_actividad_responsable_nc
    FOREIGN KEY (responsable_id) REFERENCES tbl_usuario_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_actividad_nc ADD CONSTRAINT fk_actividad_ciclo_nc
    FOREIGN KEY (ciclo_id) REFERENCES tbl_ciclo_tratamiento_nc(id)
    DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE tbl_pbi_nc ADD CONSTRAINT fk_pbi_ciclo_nc
    FOREIGN KEY (ciclo_id) REFERENCES tbl_ciclo_tratamiento_nc(id);

ALTER TABLE tbl_pbi_nc ADD CONSTRAINT fk_pbi_responsable_nc
    FOREIGN KEY (responsable_ti_id) REFERENCES tbl_usuario_nc(id);

ALTER TABLE tbl_evaluacion_eficacia_nc ADD CONSTRAINT fk_eval_ciclo_nc
    FOREIGN KEY (ciclo_id) REFERENCES tbl_ciclo_tratamiento_nc(id);

ALTER TABLE tbl_evaluacion_eficacia_nc ADD CONSTRAINT fk_eval_usuario_nc
    FOREIGN KEY (evaluador_id) REFERENCES tbl_usuario_nc(id);

ALTER TABLE tbl_comunicacion_nc ADD CONSTRAINT fk_comunicacion_ciclo_nc
    FOREIGN KEY (ciclo_id) REFERENCES tbl_ciclo_tratamiento_nc(id);

ALTER TABLE tbl_comunicacion_nc ADD CONSTRAINT fk_comunicacion_usuario_nc
    FOREIGN KEY (registrado_por_id) REFERENCES tbl_usuario_nc(id);

ALTER TABLE tbl_evidencia_nc ADD CONSTRAINT fk_evidencia_hallazgo_nc
    FOREIGN KEY (hallazgo_id) REFERENCES tbl_registro_general_nc(id);

ALTER TABLE tbl_evidencia_nc ADD CONSTRAINT fk_evidencia_accion_nc
    FOREIGN KEY (accion_id) REFERENCES tbl_actividad_nc(id);

ALTER TABLE tbl_evidencia_nc ADD CONSTRAINT fk_evidencia_analisis_nc
    FOREIGN KEY (analisis_id) REFERENCES tbl_ciclo_tratamiento_nc(id);

ALTER TABLE tbl_evidencia_nc ADD CONSTRAINT fk_evidencia_eval_nc
    FOREIGN KEY (evaluacion_id) REFERENCES tbl_evaluacion_eficacia_nc(id);

ALTER TABLE tbl_evidencia_nc ADD CONSTRAINT fk_evidencia_cierre_nc
    FOREIGN KEY (cierre_id) REFERENCES tbl_ciclo_tratamiento_nc(id);

ALTER TABLE tbl_evidencia_nc ADD CONSTRAINT fk_evidencia_usuario_nc
    FOREIGN KEY (subido_por_id) REFERENCES tbl_usuario_nc(id);

ALTER TABLE tbl_archivo_evidencia_nc ADD CONSTRAINT fk_archivo_evidencia_nc
    FOREIGN KEY (evidencia_id) REFERENCES tbl_evidencia_nc(id) ON DELETE CASCADE;

ALTER TABLE tbl_historial_hallazgo_nc ADD CONSTRAINT fk_historial_accion_nc
    FOREIGN KEY (accion_relacionada_id) REFERENCES tbl_actividad_nc(id);

ALTER TABLE tbl_historial_hallazgo_nc ADD CONSTRAINT fk_historial_hallazgo_nc
    FOREIGN KEY (hallazgo_id) REFERENCES tbl_registro_general_nc(id);

ALTER TABLE tbl_historial_hallazgo_nc ADD CONSTRAINT fk_historial_usuario_nc
    FOREIGN KEY (usuario_id) REFERENCES tbl_usuario_nc(id);

ALTER TABLE tbl_notificacion_nc ADD CONSTRAINT fk_notif_usuario_nc
    FOREIGN KEY (usuario_id) REFERENCES tbl_usuario_nc(id);

ALTER TABLE tbl_notificacion_nc ADD CONSTRAINT fk_notif_hallazgo_nc
    FOREIGN KEY (hallazgo_id) REFERENCES tbl_registro_general_nc(id);

CREATE INDEX ix_usuario_jefe_nc
    ON tbl_usuario_nc (jefe_id);
CREATE INDEX ix_proceso_responsable_nc
    ON tbl_proceso_nc (responsable_id);
CREATE INDEX ix_proc_val_usuario_nc
    ON tbl_proceso_validador_nc (usuario_id);
CREATE INDEX ix_matriz_urgencia_nc
    ON tbl_matriz_prioridad_nc (urgencia_id);
CREATE INDEX ix_matriz_prioridad_nc
    ON tbl_matriz_prioridad_nc (prioridad_id);
CREATE INDEX ix_pregunta_categoria_nc
    ON tbl_pregunta_causa_nc (categoria_id);
CREATE INDEX ix_audit_usuario_fecha_nc
    ON tbl_auditoria_administracion_nc (usuario_id, fecha DESC);
CREATE UNIQUE INDEX ux_conf_imp_default_nc
    ON tbl_configuracion_impacto_nc
       (CASE WHEN predeterminada = 1 THEN 1 ELSE NULL END);

CREATE INDEX ix_reg_estado_fecha_nc
    ON tbl_registro_general_nc (estado, fecha_registro);
CREATE INDEX ix_reg_respons_estado_nc
    ON tbl_registro_general_nc (responsable_id, estado);
CREATE INDEX ix_reg_proceso_fecha_nc
    ON tbl_registro_general_nc (proceso_id, fecha_solucion);
CREATE INDEX ix_reg_registrado_nc
    ON tbl_registro_general_nc (registrado_por_id);
CREATE INDEX ix_reg_subproceso_nc
    ON tbl_registro_general_nc (subproceso_id);
CREATE INDEX ix_reg_actualizado_nc
    ON tbl_registro_general_nc (updated_by_id);
CREATE INDEX ix_reg_tipo_nc
    ON tbl_registro_general_nc (tipo_registro_id);
CREATE INDEX ix_reg_fuente_nc
    ON tbl_registro_general_nc (fuente_deteccion_id);
CREATE INDEX ix_reg_urgencia_nc
    ON tbl_registro_general_nc (urgencia_id);
CREATE INDEX ix_reg_prioridad_nc
    ON tbl_registro_general_nc (prioridad_id);

CREATE INDEX ix_ciclo_creador_nc
    ON tbl_ciclo_tratamiento_nc (creado_por_id);
CREATE INDEX ix_ciclo_analista_nc
    ON tbl_ciclo_tratamiento_nc (analisis_responsable_id);
CREATE INDEX ix_ciclo_cierre_nc
    ON tbl_ciclo_tratamiento_nc (responsable_cierre_id);
CREATE INDEX ix_actividad_ciclo_nc
    ON tbl_actividad_nc (ciclo_id);
CREATE INDEX ix_actividad_responsable_nc
    ON tbl_actividad_nc (responsable_id);
CREATE INDEX ix_pbi_responsable_nc
    ON tbl_pbi_nc (responsable_ti_id);
CREATE INDEX ix_eval_ciclo_nc
    ON tbl_evaluacion_eficacia_nc (ciclo_id);
CREATE INDEX ix_eval_usuario_nc
    ON tbl_evaluacion_eficacia_nc (evaluador_id);
CREATE INDEX ix_comunicacion_ciclo_nc
    ON tbl_comunicacion_nc (ciclo_id);
CREATE INDEX ix_comunicacion_usuario_nc
    ON tbl_comunicacion_nc (registrado_por_id);

CREATE INDEX ix_evidencia_hallazgo_nc
    ON tbl_evidencia_nc (hallazgo_id);
CREATE INDEX ix_evidencia_accion_nc
    ON tbl_evidencia_nc (accion_id);
CREATE INDEX ix_evidencia_analisis_nc
    ON tbl_evidencia_nc (analisis_id);
CREATE INDEX ix_evidencia_eval_nc
    ON tbl_evidencia_nc (evaluacion_id);
CREATE INDEX ix_evidencia_cierre_nc
    ON tbl_evidencia_nc (cierre_id);
CREATE INDEX ix_evidencia_usuario_nc
    ON tbl_evidencia_nc (subido_por_id);
CREATE INDEX ix_historial_hall_fecha_nc
    ON tbl_historial_hallazgo_nc (hallazgo_id, fecha_hora DESC);
CREATE INDEX ix_historial_accion_nc
    ON tbl_historial_hallazgo_nc (accion_relacionada_id);
CREATE INDEX ix_historial_usuario_nc
    ON tbl_historial_hallazgo_nc (usuario_id);
CREATE INDEX ix_notif_usuario_nc
    ON tbl_notificacion_nc (usuario_id, leida, fecha_creacion DESC);
CREATE INDEX ix_notif_hallazgo_nc
    ON tbl_notificacion_nc (hallazgo_id);
CREATE INDEX ix_session_expira_nc
    ON tbl_django_session_nc (expire_date);

PROMPT OK: 44 relaciones e indices creados.
-- FIN DEL MODULO INTEGRADO: 02_relaciones_indices.sql

-- ============================================================================
-- INICIO DEL MODULO INTEGRADO: 03_triggers_integridad.sql
-- ============================================================================
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
-- FIN DEL MODULO INTEGRADO: 03_triggers_integridad.sql

-- ============================================================================
-- INICIO DEL MODULO INTEGRADO: 04_datos_base.sql
-- ============================================================================
PROMPT [4/9] Carga de catalogos y configuraciones base

INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('CATEGORIA', '1', 'Método', 1, NULL, 1);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('CATEGORIA', '2', 'Mano de Obra (Personal)', 1, NULL, 2);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('CATEGORIA', '3', 'Maquinaria (Sistemas Informáticos, Herramientas)', 1, NULL, 3);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('CATEGORIA', '4', 'Medición', 1, NULL, 4);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('CATEGORIA', '5', 'Medio de Trabajo', 1, NULL, 5);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('CATEGORIA', '6', 'Material (información)', 1, NULL, 6);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('FUENTE', 'AUDITORIA', 'Hallazgo de auditoría', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('FUENTE', 'FALLA_CRITICA', 'Falla crítica', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('FUENTE', 'LEGAL', 'Legal / Regulatorio / Contractual', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('FUENTE', 'OKR', 'Incumplimiento periódico de OKR', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('FUENTE', 'OPERACION', 'Operación / Proceso', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('FUENTE', 'OTRO', 'Otro', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('FUENTE', 'QUEJA', 'Queja / Reclamo', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('FUENTE', 'REVISION', 'Revisión de procesos', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('FUENTE', 'RIESGOS', 'Riesgos y oportunidades', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('IMPACTO', '1', 'Bajo', 1, 1, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('IMPACTO', '2', 'Medio', 1, 2, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('IMPACTO', '3', 'Alto', 1, 3, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('PRIORIDAD', 'ALTA', 'Alta', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('PRIORIDAD', 'BAJA', 'Baja', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('PRIORIDAD', 'CRITICA', 'Crítica', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('PRIORIDAD', 'MEDIA', 'Media', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('TIPO', 'INC', 'Incidente', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('TIPO', 'NOC', 'No Conforme', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('TIPO', 'PBI', 'Problema (PBI)', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('TIPO', 'SNC', 'Salida No Conforme', 1, NULL, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('URGENCIA', '1', 'Baja', 1, 1, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('URGENCIA', '2', 'Media', 1, 2, 0);
INSERT INTO tbl_catalogo_nc (clase, codigo, nombre, activo, valor, orden)
VALUES ('URGENCIA', '3', 'Alta', 1, 3, 0);

INSERT INTO tbl_configuracion_impacto_nc (
    predeterminada, clientes_bajo_desde, clientes_bajo_hasta,
    clientes_medio_desde, clientes_medio_hasta, clientes_alto_desde,
    tiempo_bajo_desde, tiempo_bajo_hasta, tiempo_medio_desde,
    tiempo_medio_hasta, tiempo_alto_desde, financiero_bajo_desde,
    financiero_bajo_hasta, financiero_medio_desde, financiero_medio_hasta,
    financiero_alto_desde
) VALUES (
    1, 0, 90, 91, 499, 500,
    0, 29, 30, 120, 121,
    0, 999999, 1000000, 1999999, 2000000
);

INSERT INTO tbl_configuracion_urgencia_nc (
    codigo, nombre, activo, tiempo_bajo_desde, tiempo_bajo_hasta,
    tiempo_medio_desde, tiempo_medio_hasta, tiempo_alto_desde
) VALUES ('FACTURACION', 'Emisión de facturación', 1, 0, 27, 28, 32, 33);
INSERT INTO tbl_configuracion_urgencia_nc (
    codigo, nombre, activo, tiempo_bajo_desde, tiempo_bajo_hasta,
    tiempo_medio_desde, tiempo_medio_hasta, tiempo_alto_desde
) VALUES ('POST_FACTURACION', 'Vencimiento de ciclo', 1, 0, 27, 28, 32, 33);

INSERT INTO tbl_matriz_prioridad_nc (impacto_id, urgencia_id, prioridad_id, activo, es_demo)
SELECT i.id, u.id, p.id, 1, 1
  FROM tbl_catalogo_nc i
  JOIN tbl_catalogo_nc u ON u.clase = 'URGENCIA' AND u.codigo = '1'
  JOIN tbl_catalogo_nc p ON p.clase = 'PRIORIDAD' AND p.codigo = 'BAJA'
 WHERE i.clase = 'IMPACTO' AND i.codigo = '1';
INSERT INTO tbl_matriz_prioridad_nc (impacto_id, urgencia_id, prioridad_id, activo, es_demo)
SELECT i.id, u.id, p.id, 1, 1
  FROM tbl_catalogo_nc i
  JOIN tbl_catalogo_nc u ON u.clase = 'URGENCIA' AND u.codigo = '2'
  JOIN tbl_catalogo_nc p ON p.clase = 'PRIORIDAD' AND p.codigo = 'MEDIA'
 WHERE i.clase = 'IMPACTO' AND i.codigo = '1';
INSERT INTO tbl_matriz_prioridad_nc (impacto_id, urgencia_id, prioridad_id, activo, es_demo)
SELECT i.id, u.id, p.id, 1, 1
  FROM tbl_catalogo_nc i
  JOIN tbl_catalogo_nc u ON u.clase = 'URGENCIA' AND u.codigo = '3'
  JOIN tbl_catalogo_nc p ON p.clase = 'PRIORIDAD' AND p.codigo = 'ALTA'
 WHERE i.clase = 'IMPACTO' AND i.codigo = '1';
INSERT INTO tbl_matriz_prioridad_nc (impacto_id, urgencia_id, prioridad_id, activo, es_demo)
SELECT i.id, u.id, p.id, 1, 1
  FROM tbl_catalogo_nc i
  JOIN tbl_catalogo_nc u ON u.clase = 'URGENCIA' AND u.codigo = '1'
  JOIN tbl_catalogo_nc p ON p.clase = 'PRIORIDAD' AND p.codigo = 'MEDIA'
 WHERE i.clase = 'IMPACTO' AND i.codigo = '2';
INSERT INTO tbl_matriz_prioridad_nc (impacto_id, urgencia_id, prioridad_id, activo, es_demo)
SELECT i.id, u.id, p.id, 1, 1
  FROM tbl_catalogo_nc i
  JOIN tbl_catalogo_nc u ON u.clase = 'URGENCIA' AND u.codigo = '2'
  JOIN tbl_catalogo_nc p ON p.clase = 'PRIORIDAD' AND p.codigo = 'ALTA'
 WHERE i.clase = 'IMPACTO' AND i.codigo = '2';
INSERT INTO tbl_matriz_prioridad_nc (impacto_id, urgencia_id, prioridad_id, activo, es_demo)
SELECT i.id, u.id, p.id, 1, 1
  FROM tbl_catalogo_nc i
  JOIN tbl_catalogo_nc u ON u.clase = 'URGENCIA' AND u.codigo = '3'
  JOIN tbl_catalogo_nc p ON p.clase = 'PRIORIDAD' AND p.codigo = 'ALTA'
 WHERE i.clase = 'IMPACTO' AND i.codigo = '2';
INSERT INTO tbl_matriz_prioridad_nc (impacto_id, urgencia_id, prioridad_id, activo, es_demo)
SELECT i.id, u.id, p.id, 1, 1
  FROM tbl_catalogo_nc i
  JOIN tbl_catalogo_nc u ON u.clase = 'URGENCIA' AND u.codigo = '1'
  JOIN tbl_catalogo_nc p ON p.clase = 'PRIORIDAD' AND p.codigo = 'ALTA'
 WHERE i.clase = 'IMPACTO' AND i.codigo = '3';
INSERT INTO tbl_matriz_prioridad_nc (impacto_id, urgencia_id, prioridad_id, activo, es_demo)
SELECT i.id, u.id, p.id, 1, 1
  FROM tbl_catalogo_nc i
  JOIN tbl_catalogo_nc u ON u.clase = 'URGENCIA' AND u.codigo = '2'
  JOIN tbl_catalogo_nc p ON p.clase = 'PRIORIDAD' AND p.codigo = 'ALTA'
 WHERE i.clase = 'IMPACTO' AND i.codigo = '3';
INSERT INTO tbl_matriz_prioridad_nc (impacto_id, urgencia_id, prioridad_id, activo, es_demo)
SELECT i.id, u.id, p.id, 1, 1
  FROM tbl_catalogo_nc i
  JOIN tbl_catalogo_nc u ON u.clase = 'URGENCIA' AND u.codigo = '3'
  JOIN tbl_catalogo_nc p ON p.clase = 'PRIORIDAD' AND p.codigo = 'CRITICA'
 WHERE i.clase = 'IMPACTO' AND i.codigo = '3';

INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '1.1', c.id, TO_NCLOB('¿Existe documentación del proceso? (política, procedimiento, instructivo, manual, etc.)'), 1, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '1';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '1.2', c.id, TO_NCLOB('¿La documentación está actualizada?'), 2, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '1';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '1.3', c.id, TO_NCLOB('¿La documentación está completa?'), 3, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '1';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '1.4', c.id, TO_NCLOB('¿La secuencia de las actividades es correcta?'), 4, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '1';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '1.5', c.id, TO_NCLOB('¿El proceso es manual o está automatizado?'), 5, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '1';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '1.6', c.id, TO_NCLOB('Otro:'), 6, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '1';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '2.1', c.id, TO_NCLOB('¿El personal tiene el perfil necesario para realizar su trabajo? (educación, formación, experiencia)'), 1, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '2';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '2.2', c.id, TO_NCLOB('¿El personal recibió entrenamiento en el puesto de trabajo?'), 2, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '2';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '2.3', c.id, TO_NCLOB('¿El personal cuenta con la experiencia necesaria para realizar su trabajo?'), 3, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '2';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '2.4', c.id, TO_NCLOB('¿El personal realizó sus actividades conforme a la documentación vigente?'), 4, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '2';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '2.5', c.id, TO_NCLOB('¿El personal trabaja fuera del horario laboral?'), 5, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '2';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '2.6', c.id, TO_NCLOB('Otro:'), 6, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '2';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '3.1', c.id, TO_NCLOB('¿Se presentaron incidentes en los sistemas? (software)'), 1, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '3';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '3.2', c.id, TO_NCLOB('¿Se presentaron incidentes en el hardware?'), 2, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '3';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '3.3', c.id, TO_NCLOB('¿Se presentaron incidentes con la red?'), 3, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '3';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '3.4', c.id, TO_NCLOB('Otro:'), 4, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '3';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '4.1', c.id, TO_NCLOB('¿Existen controles en el proceso? (Cuando exista el control completar la información requerida)'), 1, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '4';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '4.2', c.id, TO_NCLOB('¿El diseño del control es correcto? (antes, durante o después)'), 2, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '4';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '4.3', c.id, TO_NCLOB('¿El control abarca todos los aspectos a controlar?'), 3, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '4';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '4.4', c.id, TO_NCLOB('¿El control está actualizado?'), 4, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '4';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '4.5', c.id, TO_NCLOB('¿El control es manual?'), 5, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '4';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '4.6', c.id, TO_NCLOB('Otro:'), 6, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '4';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '5.1', c.id, TO_NCLOB('¿El lugar de trabajo es adecuado? (ruido, temperatura, iluminación)'), 1, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '5';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '5.2', c.id, TO_NCLOB('¿El mobiliario es adecuado?'), 2, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '5';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '5.3', c.id, TO_NCLOB('¿Requiere realizar las labores en el centro de trabajo?'), 3, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '5';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '5.4', c.id, TO_NCLOB('Otro:'), 4, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '5';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '6.1', c.id, TO_NCLOB('¿La información recibida para ejecutar el proceso es correcta?'), 1, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '6';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '6.2', c.id, TO_NCLOB('¿La información para ejecutar el proceso se recibió oportunamente?'), 2, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '6';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '6.3', c.id, TO_NCLOB('¿La información recibida para ejecutar el proceso es íntegra?'), 3, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '6';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '6.4', c.id, TO_NCLOB('¿La información se encuentra disponible cuando se requiere?'), 4, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '6';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '6.5', c.id, TO_NCLOB('¿La información depende de terceros?'), 5, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '6';
INSERT INTO tbl_pregunta_causa_nc (codigo, categoria_id, texto, orden, activo)
SELECT '6.6', c.id, TO_NCLOB('Otro:'), 6, 1
  FROM tbl_catalogo_nc c
 WHERE c.clase = 'CATEGORIA' AND c.codigo = '6';

COMMIT;

PROMPT OK: 29 catalogos, 1 matriz de impacto, 2 matrices de urgencia, 9 prioridades y 32 preguntas 6M cargadas.
-- FIN DEL MODULO INTEGRADO: 04_datos_base.sql

-- ============================================================================
-- INICIO DEL MODULO INTEGRADO: 05_baseline_django.sql
-- ============================================================================
PROMPT [5/9] Linea base de migraciones Django

-- La estructura final ya fue creada por los scripts 01 a 04.
-- Estas filas evitan que Django intente recrear el esquema al iniciar.
-- La lista fue comparada con el grafo de migraciones del codigo entregado:
-- 56 migraciones, sin faltantes ni sobrantes. No es una lista generica.

INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('accounts', '0001_initial', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('accounts', '0002_alter_usuario_options', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('accounts', '0003_remove_usuario_groups_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('accounts', '0004_usuario_direccion_usuario_gerencia_usuario_jefe', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('accounts', '0005_usuariorol', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('accounts', '0006_alter_usuario_table_alter_usuariorol_table', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0001_initial', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0002_alter_permission_name_max_length', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0003_alter_user_email_max_length', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0004_alter_user_username_opts', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0005_alter_user_last_login_null', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0006_require_contenttypes_0002', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0007_alter_validators_add_error_messages', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0008_alter_user_username_max_length', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0009_alter_user_last_name_max_length', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0010_alter_group_name_max_length', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0011_update_proxy_permissions', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('auth', '0012_alter_user_first_name_max_length', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('catalogos', '0001_initial', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('catalogos', '0002_catalogo_unificado', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('catalogos', '0003_retirar_catalogos_separados', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('catalogos', '0004_configuracionimpacto', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('catalogos', '0005_configuracionregistro_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('catalogos', '0006_alter_auditoriaadministracion_table_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('catalogos', '0007_configuracionurgencia', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('catalogos', '0008_procesovalidador', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('catalogos', '0009_delete_configuracionregistro_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('catalogos', '0010_remove_catalogo_catalogo_clase_valor_unico_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('catalogos', '0011_alter_auditoriaadministracion_table_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('contenttypes', '0001_initial', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('contenttypes', '0002_remove_content_type_name', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0001_initial', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0002_tratamiento_compacto', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0003_catalogos_tipados', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0004_registrogeneral_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0005_vista_registro_general', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0006_maximo_diez_tablas', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0007_recrear_registro_general', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0008_actividad_opcional', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0009_flujo_directo_sin_validacion', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0010_actividades_plan_flexible', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0011_impacto_configurable_registro_general', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0012_accion_inmediata_y_estados', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0013_seis_tablas_fisicas', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0014_ajustar_relaciones_compartidas', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0015_eliminar_tipos_compatibilidad', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0016_eventoregistro_delete_registrogeneral_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0017_alter_ciclotratamiento_table_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0018_snapshot_rangos_impacto', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0019_reconstruir_rangos_impacto_historicos', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0020_snapshot_urgencia', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0021_archivoevidencia', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0022_delete_eventoregistro_alter_ciclotratamiento_options_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0023_remove_correlativosac_sac_anio_ambito_unico_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('hallazgos', '0024_rename_registro_ge_estado_f20c3e_idx_tbl_registr_estado_ce0312_idx_and_more', LOCALTIMESTAMP);
INSERT INTO tbl_django_migrations_nc (app, name, applied) VALUES ('sessions', '0001_initial', LOCALTIMESTAMP);

COMMIT;

PROMPT OK: 56 migraciones Django registradas como linea base.
-- FIN DEL MODULO INTEGRADO: 05_baseline_django.sql

-- ============================================================================
-- INICIO DEL MODULO INTEGRADO: 06_ajustar_identidades.sql
-- ============================================================================
PROMPT [6/9] Ajuste de las 22 identidades al maximo cargado

-- Es obligatorio despues de insertar IDs explicitos. START WITH LIMIT VALUE
-- fija la siguiente identidad por encima del MAX(id) existente en cada tabla.

ALTER TABLE tbl_usuario_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_usuario_rol_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_catalogo_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_proceso_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_proceso_validador_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_subproceso_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_matriz_prioridad_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_configuracion_impacto_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_configuracion_urgencia_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_auditoria_administracion_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_correlativo_sac_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_registro_general_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_ciclo_tratamiento_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_actividad_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_pbi_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_evaluacion_eficacia_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_comunicacion_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_evidencia_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_archivo_evidencia_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_historial_hallazgo_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_notificacion_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

ALTER TABLE tbl_django_migrations_nc MODIFY id GENERATED BY DEFAULT ON NULL AS IDENTITY
    (START WITH LIMIT VALUE INCREMENT BY 1 CACHE 100);

PROMPT OK: 22 identidades ajustadas al limite de sus datos actuales.
-- FIN DEL MODULO INTEGRADO: 06_ajustar_identidades.sql

-- ============================================================================
-- INICIO DEL MODULO INTEGRADO: 07_permisos.sql
-- ============================================================================
PROMPT [7/9] Permisos para C27826, C28111 y C28134

GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_usuario_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_usuario_rol_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_catalogo_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_proceso_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_proceso_validador_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_subproceso_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_matriz_prioridad_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_configuracion_impacto_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_configuracion_urgencia_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_pregunta_causa_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_auditoria_administracion_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_correlativo_sac_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_registro_general_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_ciclo_tratamiento_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_actividad_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_pbi_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_evaluacion_eficacia_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_comunicacion_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_evidencia_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_archivo_evidencia_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_historial_hallazgo_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_notificacion_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_django_migrations_nc
    TO C27826, C28111, C28134;
GRANT SELECT, INSERT, UPDATE, DELETE ON tbl_django_session_nc
    TO C27826, C28111, C28134;

PROMPT OK: permisos DML concedidos sobre las 24 tablas a los 3 usuarios.
-- FIN DEL MODULO INTEGRADO: 07_permisos.sql

-- ============================================================================
-- INICIO DEL MODULO INTEGRADO: 08_prueba_humo.sql
-- ============================================================================
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
-- FIN DEL MODULO INTEGRADO: 08_prueba_humo.sql

-- ============================================================================
-- INICIO DEL MODULO INTEGRADO: 09_validacion_final.sql
-- ============================================================================
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
-- FIN DEL MODULO INTEGRADO: 09_validacion_final.sql


PROMPT ============================================================
PROMPT INSTALACION COMPLETADA Y VALIDADA
PROMPT ============================================================

EXIT SUCCESS
