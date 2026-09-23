--
-- PostgreSQL database dump
--

\restrict tCIpjayrUV7eW8HEUV740JLiyca2ss5qdDefODhuDfKMjUWfmmuaiyLd4IHYYvV

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: _aux_accounts_usuario_groups; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_accounts_usuario_groups AS (
	id bigint,
	usuario_id bigint,
	group_id integer
);


--
-- Name: _aux_accounts_usuario_user_permissions; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_accounts_usuario_user_permissions AS (
	id bigint,
	usuario_id bigint,
	permission_id integer
);


--
-- Name: _aux_auth_group; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_auth_group AS (
	id integer,
	name character varying(150)
);


--
-- Name: _aux_auth_group_permissions; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_auth_group_permissions AS (
	id bigint,
	group_id integer,
	permission_id integer
);


--
-- Name: _aux_auth_permission; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_auth_permission AS (
	id integer,
	name character varying(255),
	content_type_id integer,
	codename character varying(100)
);


--
-- Name: _aux_catalogos_auditoriaadministracion; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_catalogos_auditoriaadministracion AS (
	id bigint,
	fecha timestamp with time zone,
	entidad character varying(100),
	objeto character varying(100),
	accion character varying(40),
	antes jsonb,
	despues jsonb,
	usuario_id bigint
);


--
-- Name: _aux_catalogos_matrizprioridad; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_catalogos_matrizprioridad AS (
	id bigint,
	activo boolean,
	es_demo boolean,
	impacto_id bigint,
	urgencia_id bigint,
	prioridad_id bigint
);


--
-- Name: _aux_catalogos_preguntacausa; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_catalogos_preguntacausa AS (
	codigo character varying(8),
	texto text,
	orden smallint,
	activo boolean,
	categoria_id bigint
);


--
-- Name: _aux_catalogos_proceso_validadores; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_catalogos_proceso_validadores AS (
	id bigint,
	proceso_id bigint,
	usuario_id bigint
);


--
-- Name: _aux_catalogos_subproceso; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_catalogos_subproceso AS (
	id bigint,
	nombre character varying(180),
	activo boolean,
	proceso_id bigint
);


--
-- Name: _aux_django_admin_log; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_django_admin_log AS (
	id integer,
	action_time timestamp with time zone,
	object_id text,
	object_repr character varying(200),
	action_flag smallint,
	change_message text,
	content_type_id integer,
	user_id bigint
);


--
-- Name: _aux_django_content_type; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_django_content_type AS (
	id integer,
	app_label character varying(100),
	model character varying(100)
);


--
-- Name: _aux_django_session; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_django_session AS (
	session_key character varying(40),
	session_data text,
	expire_date timestamp with time zone
);


--
-- Name: _aux_hallazgos_comunicacionhallazgo; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_hallazgos_comunicacionhallazgo AS (
	id bigint,
	destinatarios character varying(500),
	medio character varying(120),
	descripcion text,
	fecha timestamp with time zone,
	ciclo_id bigint,
	registrado_por_id bigint
);


--
-- Name: _aux_hallazgos_evaluacioneficacia; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_hallazgos_evaluacioneficacia AS (
	id bigint,
	fecha_evaluacion date,
	resultado character varying(12),
	comentario text,
	fecha_registro timestamp with time zone,
	ciclo_id bigint,
	evaluador_id bigint
);


--
-- Name: _aux_hallazgos_evidencia; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_hallazgos_evidencia AS (
	id bigint,
	archivo character varying(100),
	nombre_original character varying(255),
	mime_type character varying(100),
	tamanio integer,
	fecha_carga timestamp with time zone,
	descripcion text,
	accion_id bigint,
	evaluacion_id bigint,
	subido_por_id bigint,
	hallazgo_id bigint,
	analisis_id bigint,
	cierre_id bigint
);


--
-- Name: _aux_hallazgos_notificacion; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_hallazgos_notificacion AS (
	id bigint,
	tipo character varying(50),
	titulo character varying(250),
	mensaje text,
	leida boolean,
	fecha_creacion timestamp with time zone,
	fecha_lectura timestamp with time zone,
	hallazgo_id bigint,
	usuario_id bigint
);


--
-- Name: _aux_hallazgos_pbi; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public._aux_hallazgos_pbi AS (
	id bigint,
	numero_pbi character varying(100),
	ticket_incidente character varying(100),
	sistema character varying(200),
	herramienta character varying(100),
	estado character varying(10),
	fecha_creacion timestamp with time zone,
	fecha_cierre date,
	observacion text,
	ciclo_id bigint,
	responsable_ti_id bigint
);


--
-- Name: sistema_registro_auxiliar_dml(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sistema_registro_auxiliar_dml() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
        DECLARE
            campo_pk text := TG_ARGV[0];
            payload jsonb;
            clave_nueva text;
            clave_anterior text;
            numero_generado bigint;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                clave_anterior := to_jsonb(OLD) ->> campo_pk;
                DELETE FROM sistema_registro_auxiliar
                 WHERE tipo = TG_TABLE_NAME AND clave = clave_anterior;
                RETURN OLD;
            END IF;

            payload := to_jsonb(NEW);
            clave_nueva := payload ->> campo_pk;
            IF clave_nueva IS NULL OR clave_nueva = '' THEN
                numero_generado := nextval(
                    pg_get_serial_sequence('sistema_registro_auxiliar', 'serial_id')
                );
                clave_nueva := numero_generado::text;
                payload := jsonb_set(payload, ARRAY[campo_pk], to_jsonb(numero_generado), true);
                NEW := jsonb_populate_record(NEW, payload);
            END IF;

            IF TG_OP = 'INSERT' THEN
                INSERT INTO sistema_registro_auxiliar(tipo, clave, datos)
                VALUES (TG_TABLE_NAME, clave_nueva, payload);
                RETURN NEW;
            END IF;

            clave_anterior := to_jsonb(OLD) ->> campo_pk;
            UPDATE sistema_registro_auxiliar
               SET clave = clave_nueva, datos = payload
             WHERE tipo = TG_TABLE_NAME AND clave = clave_anterior;
            RETURN NEW;
        END
        $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: accounts_usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts_usuario (
    id bigint NOT NULL,
    password character varying(128) NOT NULL,
    last_login timestamp with time zone,
    is_superuser boolean NOT NULL,
    username character varying(150) NOT NULL,
    first_name character varying(150) NOT NULL,
    last_name character varying(150) NOT NULL,
    email character varying(254) NOT NULL,
    is_staff boolean NOT NULL,
    is_active boolean NOT NULL,
    date_joined timestamp with time zone NOT NULL,
    area character varying(150) NOT NULL,
    cargo character varying(150) NOT NULL,
    corporate_identifier character varying(255)
);


--
-- Name: sistema_registro_auxiliar; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sistema_registro_auxiliar (
    serial_id bigint NOT NULL,
    tipo character varying(100) NOT NULL,
    clave character varying(255) NOT NULL,
    datos jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: accounts_usuario_groups; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.accounts_usuario_groups AS
 SELECT (jsonb_populate_record(NULL::public._aux_accounts_usuario_groups, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_accounts_usuario_groups, datos)).usuario_id AS usuario_id,
    (jsonb_populate_record(NULL::public._aux_accounts_usuario_groups, datos)).group_id AS group_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'accounts_usuario_groups'::text);


--
-- Name: accounts_usuario_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.accounts_usuario ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.accounts_usuario_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: accounts_usuario_user_permissions; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.accounts_usuario_user_permissions AS
 SELECT (jsonb_populate_record(NULL::public._aux_accounts_usuario_user_permissions, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_accounts_usuario_user_permissions, datos)).usuario_id AS usuario_id,
    (jsonb_populate_record(NULL::public._aux_accounts_usuario_user_permissions, datos)).permission_id AS permission_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'accounts_usuario_user_permissions'::text);


--
-- Name: auth_group; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.auth_group AS
 SELECT (jsonb_populate_record(NULL::public._aux_auth_group, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_auth_group, datos)).name AS name
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'auth_group'::text);


--
-- Name: auth_group_permissions; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.auth_group_permissions AS
 SELECT (jsonb_populate_record(NULL::public._aux_auth_group_permissions, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_auth_group_permissions, datos)).group_id AS group_id,
    (jsonb_populate_record(NULL::public._aux_auth_group_permissions, datos)).permission_id AS permission_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'auth_group_permissions'::text);


--
-- Name: auth_permission; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.auth_permission AS
 SELECT (jsonb_populate_record(NULL::public._aux_auth_permission, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_auth_permission, datos)).name AS name,
    (jsonb_populate_record(NULL::public._aux_auth_permission, datos)).content_type_id AS content_type_id,
    (jsonb_populate_record(NULL::public._aux_auth_permission, datos)).codename AS codename
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'auth_permission'::text);


--
-- Name: catalogos_auditoriaadministracion; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.catalogos_auditoriaadministracion AS
 SELECT (jsonb_populate_record(NULL::public._aux_catalogos_auditoriaadministracion, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_catalogos_auditoriaadministracion, datos)).fecha AS fecha,
    (jsonb_populate_record(NULL::public._aux_catalogos_auditoriaadministracion, datos)).entidad AS entidad,
    (jsonb_populate_record(NULL::public._aux_catalogos_auditoriaadministracion, datos)).objeto AS objeto,
    (jsonb_populate_record(NULL::public._aux_catalogos_auditoriaadministracion, datos)).accion AS accion,
    (jsonb_populate_record(NULL::public._aux_catalogos_auditoriaadministracion, datos)).antes AS antes,
    (jsonb_populate_record(NULL::public._aux_catalogos_auditoriaadministracion, datos)).despues AS despues,
    (jsonb_populate_record(NULL::public._aux_catalogos_auditoriaadministracion, datos)).usuario_id AS usuario_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'catalogos_auditoriaadministracion'::text);


--
-- Name: catalogos_catalogo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.catalogos_catalogo (
    id bigint NOT NULL,
    clase character varying(12) NOT NULL,
    codigo character varying(30) NOT NULL,
    nombre character varying(180) NOT NULL,
    activo boolean NOT NULL,
    valor smallint,
    orden smallint NOT NULL,
    CONSTRAINT catalogo_nivel_valido CHECK (((NOT ((clase)::text = ANY ((ARRAY['IMPACTO'::character varying, 'URGENCIA'::character varying])::text[]))) OR ((valor IS NOT NULL) AND ((valor >= 1) AND (valor <= 3))))),
    CONSTRAINT catalogos_catalogo_orden_check CHECK ((orden >= 0)),
    CONSTRAINT catalogos_catalogo_valor_check CHECK ((valor >= 0))
);


--
-- Name: catalogos_catalogo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.catalogos_catalogo ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.catalogos_catalogo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: catalogos_matrizprioridad; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.catalogos_matrizprioridad AS
 SELECT (jsonb_populate_record(NULL::public._aux_catalogos_matrizprioridad, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_catalogos_matrizprioridad, datos)).activo AS activo,
    (jsonb_populate_record(NULL::public._aux_catalogos_matrizprioridad, datos)).es_demo AS es_demo,
    (jsonb_populate_record(NULL::public._aux_catalogos_matrizprioridad, datos)).impacto_id AS impacto_id,
    (jsonb_populate_record(NULL::public._aux_catalogos_matrizprioridad, datos)).urgencia_id AS urgencia_id,
    (jsonb_populate_record(NULL::public._aux_catalogos_matrizprioridad, datos)).prioridad_id AS prioridad_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'catalogos_matrizprioridad'::text);


--
-- Name: catalogos_preguntacausa; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.catalogos_preguntacausa AS
 SELECT (jsonb_populate_record(NULL::public._aux_catalogos_preguntacausa, datos)).codigo AS codigo,
    (jsonb_populate_record(NULL::public._aux_catalogos_preguntacausa, datos)).texto AS texto,
    (jsonb_populate_record(NULL::public._aux_catalogos_preguntacausa, datos)).orden AS orden,
    (jsonb_populate_record(NULL::public._aux_catalogos_preguntacausa, datos)).activo AS activo,
    (jsonb_populate_record(NULL::public._aux_catalogos_preguntacausa, datos)).categoria_id AS categoria_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'catalogos_preguntacausa'::text);


--
-- Name: catalogos_proceso; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.catalogos_proceso (
    id bigint NOT NULL,
    activo boolean NOT NULL,
    nombre character varying(180) NOT NULL,
    responsable_id bigint,
    gerencia character varying(180) NOT NULL
);


--
-- Name: catalogos_proceso_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.catalogos_proceso ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.catalogos_proceso_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: catalogos_proceso_validadores; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.catalogos_proceso_validadores AS
 SELECT (jsonb_populate_record(NULL::public._aux_catalogos_proceso_validadores, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_catalogos_proceso_validadores, datos)).proceso_id AS proceso_id,
    (jsonb_populate_record(NULL::public._aux_catalogos_proceso_validadores, datos)).usuario_id AS usuario_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'catalogos_proceso_validadores'::text);


--
-- Name: catalogos_subproceso; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.catalogos_subproceso AS
 SELECT (jsonb_populate_record(NULL::public._aux_catalogos_subproceso, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_catalogos_subproceso, datos)).nombre AS nombre,
    (jsonb_populate_record(NULL::public._aux_catalogos_subproceso, datos)).activo AS activo,
    (jsonb_populate_record(NULL::public._aux_catalogos_subproceso, datos)).proceso_id AS proceso_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'catalogos_subproceso'::text);


--
-- Name: django_admin_log; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.django_admin_log AS
 SELECT (jsonb_populate_record(NULL::public._aux_django_admin_log, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_django_admin_log, datos)).action_time AS action_time,
    (jsonb_populate_record(NULL::public._aux_django_admin_log, datos)).object_id AS object_id,
    (jsonb_populate_record(NULL::public._aux_django_admin_log, datos)).object_repr AS object_repr,
    (jsonb_populate_record(NULL::public._aux_django_admin_log, datos)).action_flag AS action_flag,
    (jsonb_populate_record(NULL::public._aux_django_admin_log, datos)).change_message AS change_message,
    (jsonb_populate_record(NULL::public._aux_django_admin_log, datos)).content_type_id AS content_type_id,
    (jsonb_populate_record(NULL::public._aux_django_admin_log, datos)).user_id AS user_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'django_admin_log'::text);


--
-- Name: django_content_type; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.django_content_type AS
 SELECT (jsonb_populate_record(NULL::public._aux_django_content_type, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_django_content_type, datos)).app_label AS app_label,
    (jsonb_populate_record(NULL::public._aux_django_content_type, datos)).model AS model
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'django_content_type'::text);


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_migrations (
    id bigint NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_migrations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_migrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_session; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.django_session AS
 SELECT (jsonb_populate_record(NULL::public._aux_django_session, datos)).session_key AS session_key,
    (jsonb_populate_record(NULL::public._aux_django_session, datos)).session_data AS session_data,
    (jsonb_populate_record(NULL::public._aux_django_session, datos)).expire_date AS expire_date
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'django_session'::text);


--
-- Name: hallazgos_accion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hallazgos_accion (
    id bigint NOT NULL,
    codigo character varying(50) NOT NULL,
    tipo character varying(12) NOT NULL,
    descripcion text NOT NULL,
    fecha_inicio date NOT NULL,
    fet_inicial date NOT NULL,
    fecha_vigente date NOT NULL,
    fecha_real date,
    estado character varying(12) NOT NULL,
    porcentaje_avance smallint NOT NULL,
    resultado_esperado text NOT NULL,
    comentario text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    responsable_id bigint NOT NULL,
    ciclo_id bigint NOT NULL,
    CONSTRAINT accion_avance_max_100 CHECK ((porcentaje_avance <= 100)),
    CONSTRAINT accion_completada_coherente CHECK (((((estado)::text = 'COMPLETADA'::text) AND (fecha_real IS NOT NULL) AND (porcentaje_avance = 100)) OR ((NOT ((estado)::text = 'COMPLETADA'::text)) AND (fecha_real IS NULL) AND (porcentaje_avance < 100)))),
    CONSTRAINT accion_estado_valido CHECK (((estado)::text = ANY (ARRAY[('PENDIENTE'::character varying)::text, ('EN_PROCESO'::character varying)::text, ('COMPLETADA'::character varying)::text]))),
    CONSTRAINT accion_fet_desde_inicio CHECK ((fet_inicial >= fecha_inicio)),
    CONSTRAINT accion_real_desde_inicio CHECK (((fecha_real IS NULL) OR (fecha_real >= fecha_inicio))),
    CONSTRAINT accion_tipo_valido CHECK (((tipo)::text = ANY (ARRAY[('INMEDIATA'::character varying)::text, ('CORRECTIVA'::character varying)::text]))),
    CONSTRAINT accion_vigente_desde_inicio CHECK ((fecha_vigente >= fecha_inicio)),
    CONSTRAINT hallazgos_accion_porcentaje_avance_check CHECK ((porcentaje_avance >= 0))
);


--
-- Name: hallazgos_accion_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.hallazgos_accion ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.hallazgos_accion_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: hallazgos_ciclotratamiento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hallazgos_ciclotratamiento (
    id bigint NOT NULL,
    numero integer NOT NULL,
    motivo text NOT NULL,
    fecha_inicio timestamp with time zone NOT NULL,
    fecha_fin timestamp with time zone,
    creado_por_id bigint NOT NULL,
    hallazgo_id bigint NOT NULL,
    analisis_responsable_id bigint,
    analisis_inicio timestamp with time zone,
    analisis_fin timestamp with time zone,
    causa_raiz text NOT NULL,
    checklist_snapshot jsonb NOT NULL,
    respuestas jsonb NOT NULL,
    control jsonb NOT NULL,
    responsable_cierre_id bigint,
    fecha_cierre timestamp with time zone,
    comentarios_cierre text NOT NULL,
    resultado_cierre character varying(12) NOT NULL,
    CONSTRAINT hallazgos_ciclotratamiento_numero_check CHECK ((numero >= 0))
);


--
-- Name: hallazgos_ciclotratamiento_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.hallazgos_ciclotratamiento ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.hallazgos_ciclotratamiento_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: hallazgos_comunicacionhallazgo; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.hallazgos_comunicacionhallazgo AS
 SELECT (jsonb_populate_record(NULL::public._aux_hallazgos_comunicacionhallazgo, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_comunicacionhallazgo, datos)).destinatarios AS destinatarios,
    (jsonb_populate_record(NULL::public._aux_hallazgos_comunicacionhallazgo, datos)).medio AS medio,
    (jsonb_populate_record(NULL::public._aux_hallazgos_comunicacionhallazgo, datos)).descripcion AS descripcion,
    (jsonb_populate_record(NULL::public._aux_hallazgos_comunicacionhallazgo, datos)).fecha AS fecha,
    (jsonb_populate_record(NULL::public._aux_hallazgos_comunicacionhallazgo, datos)).ciclo_id AS ciclo_id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_comunicacionhallazgo, datos)).registrado_por_id AS registrado_por_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'hallazgos_comunicacionhallazgo'::text);


--
-- Name: hallazgos_correlativosac; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hallazgos_correlativosac (
    id bigint NOT NULL,
    anio smallint NOT NULL,
    ambito character varying(10) NOT NULL,
    ultimo_numero integer NOT NULL,
    CONSTRAINT hallazgos_correlativosac_anio_check CHECK ((anio >= 0)),
    CONSTRAINT hallazgos_correlativosac_ultimo_numero_check CHECK ((ultimo_numero >= 0))
);


--
-- Name: hallazgos_correlativosac_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.hallazgos_correlativosac ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.hallazgos_correlativosac_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: hallazgos_evaluacioneficacia; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.hallazgos_evaluacioneficacia AS
 SELECT (jsonb_populate_record(NULL::public._aux_hallazgos_evaluacioneficacia, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evaluacioneficacia, datos)).fecha_evaluacion AS fecha_evaluacion,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evaluacioneficacia, datos)).resultado AS resultado,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evaluacioneficacia, datos)).comentario AS comentario,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evaluacioneficacia, datos)).fecha_registro AS fecha_registro,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evaluacioneficacia, datos)).ciclo_id AS ciclo_id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evaluacioneficacia, datos)).evaluador_id AS evaluador_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'hallazgos_evaluacioneficacia'::text);


--
-- Name: hallazgos_evidencia; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.hallazgos_evidencia AS
 SELECT (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).archivo AS archivo,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).nombre_original AS nombre_original,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).mime_type AS mime_type,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).tamanio AS tamanio,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).fecha_carga AS fecha_carga,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).descripcion AS descripcion,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).accion_id AS accion_id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).evaluacion_id AS evaluacion_id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).subido_por_id AS subido_por_id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).hallazgo_id AS hallazgo_id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).analisis_id AS analisis_id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_evidencia, datos)).cierre_id AS cierre_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'hallazgos_evidencia'::text);


--
-- Name: hallazgos_hallazgo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hallazgos_hallazgo (
    id bigint NOT NULL,
    codigo character varying(40) NOT NULL,
    titulo character varying(250) NOT NULL,
    descripcion text NOT NULL,
    ticket_remedy character varying(120) NOT NULL,
    fecha_deteccion timestamp with time zone,
    fecha_registro timestamp with time zone NOT NULL,
    fecha_solucion date,
    impacto_clientes smallint,
    impacto_tiempo smallint,
    impacto_soles smallint,
    impacto_resultante smallint,
    prioridad_snapshot character varying(180) NOT NULL,
    aplica_impacto boolean NOT NULL,
    justificacion_no_impacto text NOT NULL,
    es_critica character varying(2) NOT NULL,
    origen_tecnologico boolean NOT NULL,
    criterio_categoria text NOT NULL,
    requisito_referencia text NOT NULL,
    version integer NOT NULL,
    updated_at timestamp with time zone NOT NULL,
    estado character varying(30) CONSTRAINT hallazgos_hallazgo_estado_id_not_null NOT NULL,
    proceso_id bigint NOT NULL,
    registrado_por_id bigint NOT NULL,
    responsable_id bigint NOT NULL,
    subproceso_id bigint,
    updated_by_id bigint,
    tipo_registro_id bigint NOT NULL,
    fuente_deteccion_id bigint,
    urgencia_id bigint,
    prioridad_id bigint,
    actividad character varying(250) NOT NULL,
    CONSTRAINT hallazgo_criticidad_valida CHECK (((es_critica)::text = ANY (ARRAY[('SI'::character varying)::text, ('NO'::character varying)::text, ('NA'::character varying)::text, (''::character varying)::text]))),
    CONSTRAINT hallazgos_hallazgo_impacto_clientes_check CHECK ((impacto_clientes >= 0)),
    CONSTRAINT hallazgos_hallazgo_impacto_resultante_check CHECK ((impacto_resultante >= 0)),
    CONSTRAINT hallazgos_hallazgo_impacto_soles_check CHECK ((impacto_soles >= 0)),
    CONSTRAINT hallazgos_hallazgo_impacto_tiempo_check CHECK ((impacto_tiempo >= 0)),
    CONSTRAINT hallazgos_hallazgo_version_check CHECK ((version >= 0)),
    CONSTRAINT impacto_clientes_rango CHECK (((impacto_clientes IS NULL) OR ((impacto_clientes >= 1) AND (impacto_clientes <= 3)))),
    CONSTRAINT impacto_resultante_rango CHECK (((impacto_resultante IS NULL) OR ((impacto_resultante >= 1) AND (impacto_resultante <= 3)))),
    CONSTRAINT impacto_soles_rango CHECK (((impacto_soles IS NULL) OR ((impacto_soles >= 1) AND (impacto_soles <= 3)))),
    CONSTRAINT impacto_tiempo_rango CHECK (((impacto_tiempo IS NULL) OR ((impacto_tiempo >= 1) AND (impacto_tiempo <= 3))))
);


--
-- Name: hallazgos_hallazgo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.hallazgos_hallazgo ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.hallazgos_hallazgo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: hallazgos_historialhallazgo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.hallazgos_historialhallazgo (
    id bigint NOT NULL,
    fecha_hora timestamp with time zone NOT NULL,
    accion character varying(70) NOT NULL,
    estado_anterior character varying(30) NOT NULL,
    estado_nuevo character varying(30) NOT NULL,
    comentario text NOT NULL,
    metadata_json jsonb NOT NULL,
    hallazgo_id bigint NOT NULL,
    usuario_id bigint NOT NULL,
    accion_relacionada_id bigint
);


--
-- Name: hallazgos_historialhallazgo_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.hallazgos_historialhallazgo ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.hallazgos_historialhallazgo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: hallazgos_notificacion; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.hallazgos_notificacion AS
 SELECT (jsonb_populate_record(NULL::public._aux_hallazgos_notificacion, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_notificacion, datos)).tipo AS tipo,
    (jsonb_populate_record(NULL::public._aux_hallazgos_notificacion, datos)).titulo AS titulo,
    (jsonb_populate_record(NULL::public._aux_hallazgos_notificacion, datos)).mensaje AS mensaje,
    (jsonb_populate_record(NULL::public._aux_hallazgos_notificacion, datos)).leida AS leida,
    (jsonb_populate_record(NULL::public._aux_hallazgos_notificacion, datos)).fecha_creacion AS fecha_creacion,
    (jsonb_populate_record(NULL::public._aux_hallazgos_notificacion, datos)).fecha_lectura AS fecha_lectura,
    (jsonb_populate_record(NULL::public._aux_hallazgos_notificacion, datos)).hallazgo_id AS hallazgo_id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_notificacion, datos)).usuario_id AS usuario_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'hallazgos_notificacion'::text);


--
-- Name: hallazgos_pbi; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.hallazgos_pbi AS
 SELECT (jsonb_populate_record(NULL::public._aux_hallazgos_pbi, datos)).id AS id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_pbi, datos)).numero_pbi AS numero_pbi,
    (jsonb_populate_record(NULL::public._aux_hallazgos_pbi, datos)).ticket_incidente AS ticket_incidente,
    (jsonb_populate_record(NULL::public._aux_hallazgos_pbi, datos)).sistema AS sistema,
    (jsonb_populate_record(NULL::public._aux_hallazgos_pbi, datos)).herramienta AS herramienta,
    (jsonb_populate_record(NULL::public._aux_hallazgos_pbi, datos)).estado AS estado,
    (jsonb_populate_record(NULL::public._aux_hallazgos_pbi, datos)).fecha_creacion AS fecha_creacion,
    (jsonb_populate_record(NULL::public._aux_hallazgos_pbi, datos)).fecha_cierre AS fecha_cierre,
    (jsonb_populate_record(NULL::public._aux_hallazgos_pbi, datos)).observacion AS observacion,
    (jsonb_populate_record(NULL::public._aux_hallazgos_pbi, datos)).ciclo_id AS ciclo_id,
    (jsonb_populate_record(NULL::public._aux_hallazgos_pbi, datos)).responsable_ti_id AS responsable_ti_id
   FROM public.sistema_registro_auxiliar
  WHERE ((tipo)::text = 'hallazgos_pbi'::text);


--
-- Name: registro_general; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.registro_general AS
 SELECT concat(h.id, ':', COALESCE(c.id, (0)::bigint), ':', COALESCE(a.id, (0)::bigint)) AS fila_id,
    h.id AS hallazgo_id,
    c.id AS ciclo_id,
    a.id AS accion_id,
    row_number() OVER (ORDER BY h.id, c.numero NULLS FIRST, a.id NULLS FIRST) AS numero,
    p.gerencia,
    p.nombre AS proceso,
    COALESCE(sp.nombre, ''::character varying) AS sub_proceso,
    COALESCE(f.nombre, ''::character varying) AS fuente_deteccion,
    t.nombre AS tipo_hallazgo,
    h.codigo AS numero_hallazgo,
    h.ticket_remedy,
    h.descripcion AS descripcion_hallazgo,
    h.requisito_referencia,
    COALESCE(NULLIF(TRIM(BOTH FROM concat_ws(' '::text, rp.first_name, rp.last_name)), ''::text), (rp.username)::text, ''::text) AS responsable_proceso,
    h.fecha_deteccion,
    h.fecha_registro,
        CASE
            WHEN (NOT h.aplica_impacto) THEN 'No aplica'::character varying
            ELSE COALESCE(i.nombre, ''::character varying)
        END AS impacto,
        CASE
            WHEN (NOT h.aplica_impacto) THEN 'No aplica'::character varying
            ELSE COALESCE(u.nombre, ''::character varying)
        END AS urgencia,
    h.prioridad_snapshot AS prioridad_criticidad,
        CASE h.es_critica
            WHEN 'SI'::text THEN 'Sí'::text
            WHEN 'NO'::text THEN 'No'::text
            WHEN 'NA'::text THEN 'No aplica'::text
            ELSE ''::text
        END AS no_conformidad_critica,
    COALESCE(c.causa_raiz, ''::text) AS causas_raiz,
        CASE a.tipo
            WHEN 'INMEDIATA'::text THEN 'Acción inmediata'::text
            WHEN 'CORRECTIVA'::text THEN 'Acción correctiva'::text
            ELSE ''::text
        END AS tipo_accion,
    COALESCE(a.descripcion, ''::text) AS descripcion_accion,
    COALESCE(NULLIF(TRIM(BOTH FROM concat_ws(' '::text, ra.first_name, ra.last_name)), ''::text), (ra.username)::text, ''::text) AS responsable,
    a.fecha_vigente AS fet,
        CASE a.estado
            WHEN 'PENDIENTE'::text THEN 'Pendiente'::character varying
            WHEN 'EN_PROCESO'::text THEN 'En proceso'::character varying
            WHEN 'COMPLETADA'::text THEN 'Completada'::character varying
            ELSE
            CASE h.estado
                WHEN 'BORRADOR'::text THEN 'Borrador'::character varying
                WHEN 'PENDIENTE_VALIDACION'::text THEN 'Pendiente de validación'::character varying
                WHEN 'DEVUELTO'::text THEN 'Devuelto'::character varying
                WHEN 'VALIDADO'::text THEN 'Validado'::character varying
                WHEN 'ACCION_INMEDIATA'::text THEN 'Acción inmediata'::character varying
                WHEN 'EN_ANALISIS'::text THEN 'En análisis'::character varying
                WHEN 'PBI_EN_GESTION'::text THEN 'PBI en gestión'::character varying
                WHEN 'PLAN_ACCION'::text THEN 'Plan de acción'::character varying
                WHEN 'EN_IMPLEMENTACION'::text THEN 'En implementación'::character varying
                WHEN 'EN_VERIFICACION'::text THEN 'En verificación'::character varying
                WHEN 'CERRADO'::text THEN 'Cerrado'::character varying
                WHEN 'REABIERTO'::text THEN 'Reabierto'::character varying
                WHEN 'CANCELADO'::text THEN 'Cancelado'::character varying
                ELSE h.estado
            END
        END AS estado,
    COALESCE(ev.nombres, ''::text) AS evidencia_implementacion,
    a.porcentaje_avance,
    COALESCE(a.comentario, ''::text) AS comentario,
    e.fecha_evaluacion AS fecha_evaluacion_eficacia,
        CASE e.resultado
            WHEN 'EFICAZ'::text THEN 'Eficaz'::text
            WHEN 'NO_EFICAZ'::text THEN 'No eficaz'::text
            ELSE ''::text
        END AS resultado_eficacia,
    c.fecha_cierre,
    COALESCE(NULLIF(TRIM(BOTH FROM concat_ws(' '::text, verificador.first_name, verificador.last_name)), ''::text), (verificador.username)::text, ''::text) AS auditor_verificador,
    concat_ws('
'::text,
        CASE
            WHEN (e.comentario IS NOT NULL) THEN ('Evaluación: '::text || e.comentario)
            ELSE NULL::text
        END,
        CASE
            WHEN (c.comentarios_cierre <> ''::text) THEN ('Cierre: '::text || c.comentarios_cierre)
            ELSE NULL::text
        END) AS comentarios
   FROM ((((((((((((((public.hallazgos_hallazgo h
     JOIN public.catalogos_proceso p ON ((p.id = h.proceso_id)))
     LEFT JOIN public.catalogos_subproceso sp ON ((sp.id = h.subproceso_id)))
     JOIN public.catalogos_catalogo t ON ((t.id = h.tipo_registro_id)))
     LEFT JOIN public.catalogos_catalogo f ON ((f.id = h.fuente_deteccion_id)))
     LEFT JOIN public.catalogos_catalogo u ON ((u.id = h.urgencia_id)))
     LEFT JOIN public.catalogos_catalogo i ON ((((i.clase)::text = 'IMPACTO'::text) AND (i.valor = h.impacto_resultante))))
     LEFT JOIN public.accounts_usuario rp ON ((rp.id = p.responsable_id)))
     LEFT JOIN public.hallazgos_ciclotratamiento c ON ((c.hallazgo_id = h.id)))
     LEFT JOIN public.hallazgos_accion a ON ((a.ciclo_id = c.id)))
     LEFT JOIN public.accounts_usuario ra ON ((ra.id = a.responsable_id)))
     LEFT JOIN LATERAL ( SELECT ee.id,
            ee.fecha_evaluacion,
            ee.resultado,
            ee.comentario,
            ee.fecha_registro,
            ee.ciclo_id,
            ee.evaluador_id
           FROM public.hallazgos_evaluacioneficacia ee
          WHERE (ee.ciclo_id = c.id)
          ORDER BY ee.fecha_registro DESC, ee.id DESC
         LIMIT 1) e ON (true))
     LEFT JOIN LATERAL ( SELECT hh.usuario_id
           FROM public.hallazgos_historialhallazgo hh
          WHERE ((hh.hallazgo_id = h.id) AND ((hh.accion)::text = 'VALIDAR'::text))
          ORDER BY hh.fecha_hora DESC, hh.id DESC
         LIMIT 1) val ON (true))
     LEFT JOIN public.accounts_usuario verificador ON ((verificador.id = COALESCE(e.evaluador_id, c.responsable_cierre_id, val.usuario_id))))
     LEFT JOIN LATERAL ( SELECT string_agg((evi.nombre_original)::text, '
'::text ORDER BY evi.id) AS nombres
           FROM public.hallazgos_evidencia evi
          WHERE ((evi.hallazgo_id = h.id) AND ((evi.accion_id = a.id) OR ((a.id IS NULL) AND (evi.accion_id IS NULL) AND (evi.analisis_id IS NULL) AND (evi.evaluacion_id IS NULL) AND (evi.cierre_id IS NULL))))) ev ON (true));


--
-- Name: sistema_registro_auxiliar_serial_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.sistema_registro_auxiliar ALTER COLUMN serial_id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.sistema_registro_auxiliar_serial_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: accounts_usuario accounts_usuario_corporate_identifier_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_usuario
    ADD CONSTRAINT accounts_usuario_corporate_identifier_key UNIQUE (corporate_identifier);


--
-- Name: accounts_usuario accounts_usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_usuario
    ADD CONSTRAINT accounts_usuario_pkey PRIMARY KEY (id);


--
-- Name: accounts_usuario accounts_usuario_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts_usuario
    ADD CONSTRAINT accounts_usuario_username_key UNIQUE (username);


--
-- Name: catalogos_catalogo catalogo_clase_codigo_unico; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.catalogos_catalogo
    ADD CONSTRAINT catalogo_clase_codigo_unico UNIQUE (clase, codigo);


--
-- Name: catalogos_catalogo catalogo_clase_valor_unico; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.catalogos_catalogo
    ADD CONSTRAINT catalogo_clase_valor_unico UNIQUE (clase, valor);


--
-- Name: catalogos_catalogo catalogos_catalogo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.catalogos_catalogo
    ADD CONSTRAINT catalogos_catalogo_pkey PRIMARY KEY (id);


--
-- Name: catalogos_proceso catalogos_proceso_nombre_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.catalogos_proceso
    ADD CONSTRAINT catalogos_proceso_nombre_key UNIQUE (nombre);


--
-- Name: catalogos_proceso catalogos_proceso_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.catalogos_proceso
    ADD CONSTRAINT catalogos_proceso_pkey PRIMARY KEY (id);


--
-- Name: hallazgos_ciclotratamiento ciclo_hallazgo_numero_unico; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_ciclotratamiento
    ADD CONSTRAINT ciclo_hallazgo_numero_unico UNIQUE (hallazgo_id, numero);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: hallazgos_accion hallazgos_accion_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_accion
    ADD CONSTRAINT hallazgos_accion_codigo_key UNIQUE (codigo);


--
-- Name: hallazgos_accion hallazgos_accion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_accion
    ADD CONSTRAINT hallazgos_accion_pkey PRIMARY KEY (id);


--
-- Name: hallazgos_ciclotratamiento hallazgos_ciclotratamiento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_ciclotratamiento
    ADD CONSTRAINT hallazgos_ciclotratamiento_pkey PRIMARY KEY (id);


--
-- Name: hallazgos_correlativosac hallazgos_correlativosac_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_correlativosac
    ADD CONSTRAINT hallazgos_correlativosac_pkey PRIMARY KEY (id);


--
-- Name: hallazgos_hallazgo hallazgos_hallazgo_codigo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_hallazgo
    ADD CONSTRAINT hallazgos_hallazgo_codigo_key UNIQUE (codigo);


--
-- Name: hallazgos_hallazgo hallazgos_hallazgo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_hallazgo
    ADD CONSTRAINT hallazgos_hallazgo_pkey PRIMARY KEY (id);


--
-- Name: hallazgos_historialhallazgo hallazgos_historialhallazgo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_historialhallazgo
    ADD CONSTRAINT hallazgos_historialhallazgo_pkey PRIMARY KEY (id);


--
-- Name: hallazgos_correlativosac sac_anio_ambito_unico; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_correlativosac
    ADD CONSTRAINT sac_anio_ambito_unico UNIQUE (anio, ambito);


--
-- Name: sistema_registro_auxiliar sistema_registro_auxiliar_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sistema_registro_auxiliar
    ADD CONSTRAINT sistema_registro_auxiliar_pk PRIMARY KEY (tipo, clave);


--
-- Name: accounts_usuario_corporate_identifier_a00de3b9_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_usuario_corporate_identifier_a00de3b9_like ON public.accounts_usuario USING btree (corporate_identifier varchar_pattern_ops);


--
-- Name: accounts_usuario_username_c366c69f_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX accounts_usuario_username_c366c69f_like ON public.accounts_usuario USING btree (username varchar_pattern_ops);


--
-- Name: catalogos_proceso_nombre_fd91997b_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX catalogos_proceso_nombre_fd91997b_like ON public.catalogos_proceso USING btree (nombre varchar_pattern_ops);


--
-- Name: catalogos_proceso_responsable_id_9ca91c92; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX catalogos_proceso_responsable_id_9ca91c92 ON public.catalogos_proceso USING btree (responsable_id);


--
-- Name: hallazgos_accion_ciclo_id_2055bb12; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_accion_ciclo_id_2055bb12 ON public.hallazgos_accion USING btree (ciclo_id);


--
-- Name: hallazgos_accion_codigo_1f1a0772_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_accion_codigo_1f1a0772_like ON public.hallazgos_accion USING btree (codigo varchar_pattern_ops);


--
-- Name: hallazgos_accion_responsable_id_e98a4954; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_accion_responsable_id_e98a4954 ON public.hallazgos_accion USING btree (responsable_id);


--
-- Name: hallazgos_ciclotratamiento_analisis_responsable_id_2d85dcfa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_ciclotratamiento_analisis_responsable_id_2d85dcfa ON public.hallazgos_ciclotratamiento USING btree (analisis_responsable_id);


--
-- Name: hallazgos_ciclotratamiento_creado_por_id_58c1e7cf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_ciclotratamiento_creado_por_id_58c1e7cf ON public.hallazgos_ciclotratamiento USING btree (creado_por_id);


--
-- Name: hallazgos_ciclotratamiento_hallazgo_id_ee689a58; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_ciclotratamiento_hallazgo_id_ee689a58 ON public.hallazgos_ciclotratamiento USING btree (hallazgo_id);


--
-- Name: hallazgos_ciclotratamiento_responsable_cierre_id_e8a26f3e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_ciclotratamiento_responsable_cierre_id_e8a26f3e ON public.hallazgos_ciclotratamiento USING btree (responsable_cierre_id);


--
-- Name: hallazgos_h_estado_7a4480_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_h_estado_7a4480_idx ON public.hallazgos_hallazgo USING btree (estado, fecha_registro);


--
-- Name: hallazgos_h_proceso_3a856a_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_h_proceso_3a856a_idx ON public.hallazgos_hallazgo USING btree (proceso_id, fecha_solucion);


--
-- Name: hallazgos_h_respons_f759c0_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_h_respons_f759c0_idx ON public.hallazgos_hallazgo USING btree (responsable_id, estado);


--
-- Name: hallazgos_hallazgo_codigo_54cc5b0a_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_hallazgo_codigo_54cc5b0a_like ON public.hallazgos_hallazgo USING btree (codigo varchar_pattern_ops);


--
-- Name: hallazgos_hallazgo_fuente_deteccion_id_9bc417fc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_hallazgo_fuente_deteccion_id_9bc417fc ON public.hallazgos_hallazgo USING btree (fuente_deteccion_id);


--
-- Name: hallazgos_hallazgo_prioridad_id_9335da0c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_hallazgo_prioridad_id_9335da0c ON public.hallazgos_hallazgo USING btree (prioridad_id);


--
-- Name: hallazgos_hallazgo_proceso_id_8b5bdc59; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_hallazgo_proceso_id_8b5bdc59 ON public.hallazgos_hallazgo USING btree (proceso_id);


--
-- Name: hallazgos_hallazgo_registrado_por_id_ceae8bdd; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_hallazgo_registrado_por_id_ceae8bdd ON public.hallazgos_hallazgo USING btree (registrado_por_id);


--
-- Name: hallazgos_hallazgo_responsable_id_1ac2c44b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_hallazgo_responsable_id_1ac2c44b ON public.hallazgos_hallazgo USING btree (responsable_id);


--
-- Name: hallazgos_hallazgo_subproceso_id_74727620; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_hallazgo_subproceso_id_74727620 ON public.hallazgos_hallazgo USING btree (subproceso_id);


--
-- Name: hallazgos_hallazgo_tipo_registro_id_25e04da9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_hallazgo_tipo_registro_id_25e04da9 ON public.hallazgos_hallazgo USING btree (tipo_registro_id);


--
-- Name: hallazgos_hallazgo_updated_by_id_3981db0c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_hallazgo_updated_by_id_3981db0c ON public.hallazgos_hallazgo USING btree (updated_by_id);


--
-- Name: hallazgos_hallazgo_urgencia_id_9d147ef0; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_hallazgo_urgencia_id_9d147ef0 ON public.hallazgos_hallazgo USING btree (urgencia_id);


--
-- Name: hallazgos_historialhallazgo_accion_relacionada_id_130b7038; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_historialhallazgo_accion_relacionada_id_130b7038 ON public.hallazgos_historialhallazgo USING btree (accion_relacionada_id);


--
-- Name: hallazgos_historialhallazgo_hallazgo_id_0dae44b7; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_historialhallazgo_hallazgo_id_0dae44b7 ON public.hallazgos_historialhallazgo USING btree (hallazgo_id);


--
-- Name: hallazgos_historialhallazgo_usuario_id_26917eee; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX hallazgos_historialhallazgo_usuario_id_26917eee ON public.hallazgos_historialhallazgo USING btree (usuario_id);


--
-- Name: accounts_usuario_groups auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.accounts_usuario_groups FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: accounts_usuario_user_permissions auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.accounts_usuario_user_permissions FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: auth_group auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.auth_group FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: auth_group_permissions auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.auth_group_permissions FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: auth_permission auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.auth_permission FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: catalogos_auditoriaadministracion auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.catalogos_auditoriaadministracion FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: catalogos_matrizprioridad auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.catalogos_matrizprioridad FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: catalogos_preguntacausa auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.catalogos_preguntacausa FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('codigo');


--
-- Name: catalogos_proceso_validadores auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.catalogos_proceso_validadores FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: catalogos_subproceso auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.catalogos_subproceso FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: django_admin_log auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.django_admin_log FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: django_content_type auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.django_content_type FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: django_session auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.django_session FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('session_key');


--
-- Name: hallazgos_comunicacionhallazgo auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.hallazgos_comunicacionhallazgo FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: hallazgos_evaluacioneficacia auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.hallazgos_evaluacioneficacia FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: hallazgos_evidencia auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.hallazgos_evidencia FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: hallazgos_notificacion auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.hallazgos_notificacion FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: hallazgos_pbi auxiliar_dml; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER auxiliar_dml INSTEAD OF INSERT OR DELETE OR UPDATE ON public.hallazgos_pbi FOR EACH ROW EXECUTE FUNCTION public.sistema_registro_auxiliar_dml('id');


--
-- Name: catalogos_proceso catalogos_proceso_responsable_id_9ca91c92_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.catalogos_proceso
    ADD CONSTRAINT catalogos_proceso_responsable_id_9ca91c92_fk_accounts_ FOREIGN KEY (responsable_id) REFERENCES public.accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_accion hallazgos_accion_ciclo_id_2055bb12_fk_hallazgos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_accion
    ADD CONSTRAINT hallazgos_accion_ciclo_id_2055bb12_fk_hallazgos FOREIGN KEY (ciclo_id) REFERENCES public.hallazgos_ciclotratamiento(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_accion hallazgos_accion_responsable_id_e98a4954_fk_accounts_usuario_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_accion
    ADD CONSTRAINT hallazgos_accion_responsable_id_e98a4954_fk_accounts_usuario_id FOREIGN KEY (responsable_id) REFERENCES public.accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_ciclotratamiento hallazgos_ciclotrata_analisis_responsable_2d85dcfa_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_ciclotratamiento
    ADD CONSTRAINT hallazgos_ciclotrata_analisis_responsable_2d85dcfa_fk_accounts_ FOREIGN KEY (analisis_responsable_id) REFERENCES public.accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_ciclotratamiento hallazgos_ciclotrata_creado_por_id_58c1e7cf_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_ciclotratamiento
    ADD CONSTRAINT hallazgos_ciclotrata_creado_por_id_58c1e7cf_fk_accounts_ FOREIGN KEY (creado_por_id) REFERENCES public.accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_ciclotratamiento hallazgos_ciclotrata_hallazgo_id_ee689a58_fk_hallazgos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_ciclotratamiento
    ADD CONSTRAINT hallazgos_ciclotrata_hallazgo_id_ee689a58_fk_hallazgos FOREIGN KEY (hallazgo_id) REFERENCES public.hallazgos_hallazgo(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_ciclotratamiento hallazgos_ciclotrata_responsable_cierre_i_e8a26f3e_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_ciclotratamiento
    ADD CONSTRAINT hallazgos_ciclotrata_responsable_cierre_i_e8a26f3e_fk_accounts_ FOREIGN KEY (responsable_cierre_id) REFERENCES public.accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_hallazgo hallazgos_hallazgo_fuente_deteccion_id_9bc417fc_fk_catalogos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_hallazgo
    ADD CONSTRAINT hallazgos_hallazgo_fuente_deteccion_id_9bc417fc_fk_catalogos FOREIGN KEY (fuente_deteccion_id) REFERENCES public.catalogos_catalogo(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_hallazgo hallazgos_hallazgo_prioridad_id_9335da0c_fk_catalogos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_hallazgo
    ADD CONSTRAINT hallazgos_hallazgo_prioridad_id_9335da0c_fk_catalogos FOREIGN KEY (prioridad_id) REFERENCES public.catalogos_catalogo(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_hallazgo hallazgos_hallazgo_proceso_id_8b5bdc59_fk_catalogos_proceso_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_hallazgo
    ADD CONSTRAINT hallazgos_hallazgo_proceso_id_8b5bdc59_fk_catalogos_proceso_id FOREIGN KEY (proceso_id) REFERENCES public.catalogos_proceso(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_hallazgo hallazgos_hallazgo_registrado_por_id_ceae8bdd_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_hallazgo
    ADD CONSTRAINT hallazgos_hallazgo_registrado_por_id_ceae8bdd_fk_accounts_ FOREIGN KEY (registrado_por_id) REFERENCES public.accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_hallazgo hallazgos_hallazgo_responsable_id_1ac2c44b_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_hallazgo
    ADD CONSTRAINT hallazgos_hallazgo_responsable_id_1ac2c44b_fk_accounts_ FOREIGN KEY (responsable_id) REFERENCES public.accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_hallazgo hallazgos_hallazgo_tipo_registro_id_25e04da9_fk_catalogos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_hallazgo
    ADD CONSTRAINT hallazgos_hallazgo_tipo_registro_id_25e04da9_fk_catalogos FOREIGN KEY (tipo_registro_id) REFERENCES public.catalogos_catalogo(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_hallazgo hallazgos_hallazgo_updated_by_id_3981db0c_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_hallazgo
    ADD CONSTRAINT hallazgos_hallazgo_updated_by_id_3981db0c_fk_accounts_ FOREIGN KEY (updated_by_id) REFERENCES public.accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_hallazgo hallazgos_hallazgo_urgencia_id_9d147ef0_fk_catalogos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_hallazgo
    ADD CONSTRAINT hallazgos_hallazgo_urgencia_id_9d147ef0_fk_catalogos FOREIGN KEY (urgencia_id) REFERENCES public.catalogos_catalogo(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_historialhallazgo hallazgos_historialh_accion_relacionada_i_130b7038_fk_hallazgos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_historialhallazgo
    ADD CONSTRAINT hallazgos_historialh_accion_relacionada_i_130b7038_fk_hallazgos FOREIGN KEY (accion_relacionada_id) REFERENCES public.hallazgos_accion(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_historialhallazgo hallazgos_historialh_hallazgo_id_0dae44b7_fk_hallazgos; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_historialhallazgo
    ADD CONSTRAINT hallazgos_historialh_hallazgo_id_0dae44b7_fk_hallazgos FOREIGN KEY (hallazgo_id) REFERENCES public.hallazgos_hallazgo(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: hallazgos_historialhallazgo hallazgos_historialh_usuario_id_26917eee_fk_accounts_; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.hallazgos_historialhallazgo
    ADD CONSTRAINT hallazgos_historialh_usuario_id_26917eee_fk_accounts_ FOREIGN KEY (usuario_id) REFERENCES public.accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;


--
-- PostgreSQL database dump complete
--

\unrestrict tCIpjayrUV7eW8HEUV740JLiyca2ss5qdDefODhuDfKMjUWfmmuaiyLd4IHYYvV

