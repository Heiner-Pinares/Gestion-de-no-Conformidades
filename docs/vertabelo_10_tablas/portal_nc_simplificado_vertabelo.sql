-- Portal NC simplificado: tablas fisicas para Vertabelo, PostgreSQL.
-- Solo estructura. No ejecutar en la base existente.
-- Incluye columnas, nulabilidad, claves primarias, unicas y relaciones.
-- Las identidades se representan como serial/bigserial para importar.
-- El esquema original adjunto conserva checks, indices, identidades y la vista registro_general.

CREATE TABLE "accounts_usuario" (
    "id" bigserial NOT NULL,
    "password" character varying(128) NOT NULL,
    "last_login" timestamp with time zone,
    "is_superuser" boolean NOT NULL,
    "username" character varying(150) NOT NULL,
    "first_name" character varying(150) NOT NULL,
    "last_name" character varying(150) NOT NULL,
    "email" character varying(254) NOT NULL,
    "is_staff" boolean NOT NULL,
    "is_active" boolean NOT NULL,
    "date_joined" timestamp with time zone NOT NULL,
    "area" character varying(150) NOT NULL,
    "cargo" character varying(150) NOT NULL,
    "corporate_identifier" character varying(255)
);

CREATE TABLE "catalogos_catalogo" (
    "id" bigserial NOT NULL,
    "clase" character varying(12) NOT NULL,
    "codigo" character varying(30) NOT NULL,
    "nombre" character varying(180) NOT NULL,
    "activo" boolean NOT NULL,
    "valor" smallint,
    "orden" smallint NOT NULL
);

CREATE TABLE "catalogos_proceso" (
    "id" bigserial NOT NULL,
    "activo" boolean NOT NULL,
    "nombre" character varying(180) NOT NULL,
    "responsable_id" bigint,
    "gerencia" character varying(180) NOT NULL
);

CREATE TABLE "django_migrations" (
    "id" bigserial NOT NULL,
    "app" character varying(255) NOT NULL,
    "name" character varying(255) NOT NULL,
    "applied" timestamp with time zone NOT NULL
);

CREATE TABLE "hallazgos_accion" (
    "id" bigserial NOT NULL,
    "codigo" character varying(50) NOT NULL,
    "tipo" character varying(12) NOT NULL,
    "descripcion" text NOT NULL,
    "fecha_inicio" date NOT NULL,
    "fet_inicial" date NOT NULL,
    "fecha_vigente" date NOT NULL,
    "fecha_real" date,
    "estado" character varying(12) NOT NULL,
    "porcentaje_avance" smallint NOT NULL,
    "resultado_esperado" text NOT NULL,
    "comentario" text NOT NULL,
    "created_at" timestamp with time zone NOT NULL,
    "updated_at" timestamp with time zone NOT NULL,
    "responsable_id" bigint NOT NULL,
    "ciclo_id" bigint NOT NULL
);

CREATE TABLE "hallazgos_ciclotratamiento" (
    "id" bigserial NOT NULL,
    "numero" integer NOT NULL,
    "motivo" text NOT NULL,
    "fecha_inicio" timestamp with time zone NOT NULL,
    "fecha_fin" timestamp with time zone,
    "creado_por_id" bigint NOT NULL,
    "hallazgo_id" bigint NOT NULL,
    "analisis_responsable_id" bigint,
    "analisis_inicio" timestamp with time zone,
    "analisis_fin" timestamp with time zone,
    "causa_raiz" text NOT NULL,
    "checklist_snapshot" jsonb NOT NULL,
    "respuestas" jsonb NOT NULL,
    "control" jsonb NOT NULL,
    "responsable_cierre_id" bigint,
    "fecha_cierre" timestamp with time zone,
    "comentarios_cierre" text NOT NULL,
    "resultado_cierre" character varying(12) NOT NULL
);

CREATE TABLE "hallazgos_correlativosac" (
    "id" bigserial NOT NULL,
    "anio" smallint NOT NULL,
    "ambito" character varying(10) NOT NULL,
    "ultimo_numero" integer NOT NULL
);

CREATE TABLE "hallazgos_hallazgo" (
    "id" bigserial NOT NULL,
    "codigo" character varying(40) NOT NULL,
    "titulo" character varying(250) NOT NULL,
    "descripcion" text NOT NULL,
    "ticket_remedy" character varying(120) NOT NULL,
    "fecha_deteccion" timestamp with time zone,
    "fecha_registro" timestamp with time zone NOT NULL,
    "fecha_solucion" date,
    "impacto_clientes" smallint,
    "impacto_tiempo" smallint,
    "impacto_soles" smallint,
    "impacto_resultante" smallint,
    "prioridad_snapshot" character varying(180) NOT NULL,
    "aplica_impacto" boolean NOT NULL,
    "justificacion_no_impacto" text NOT NULL,
    "es_critica" character varying(2) NOT NULL,
    "origen_tecnologico" boolean NOT NULL,
    "criterio_categoria" text NOT NULL,
    "requisito_referencia" text NOT NULL,
    "version" integer NOT NULL,
    "updated_at" timestamp with time zone NOT NULL,
    "estado" character varying(30) NOT NULL,
    "proceso_id" bigint NOT NULL,
    "registrado_por_id" bigint NOT NULL,
    "responsable_id" bigint NOT NULL,
    "subproceso_id" bigint,
    "updated_by_id" bigint,
    "tipo_registro_id" bigint NOT NULL,
    "fuente_deteccion_id" bigint,
    "urgencia_id" bigint,
    "prioridad_id" bigint,
    "actividad" character varying(250) NOT NULL
);

CREATE TABLE "hallazgos_historialhallazgo" (
    "id" bigserial NOT NULL,
    "fecha_hora" timestamp with time zone NOT NULL,
    "accion" character varying(70) NOT NULL,
    "estado_anterior" character varying(30) NOT NULL,
    "estado_nuevo" character varying(30) NOT NULL,
    "comentario" text NOT NULL,
    "metadata_json" jsonb NOT NULL,
    "hallazgo_id" bigint NOT NULL,
    "usuario_id" bigint NOT NULL,
    "accion_relacionada_id" bigint
);

CREATE TABLE "sistema_registro_auxiliar" (
    "serial_id" bigserial NOT NULL,
    "tipo" character varying(100) NOT NULL,
    "clave" character varying(255) NOT NULL,
    "datos" jsonb DEFAULT '{}'::jsonb NOT NULL
);

ALTER TABLE "accounts_usuario" ADD CONSTRAINT "accounts_usuario_corporate_identifier_key" UNIQUE (corporate_identifier);
ALTER TABLE "accounts_usuario" ADD CONSTRAINT "accounts_usuario_pkey" PRIMARY KEY (id);
ALTER TABLE "accounts_usuario" ADD CONSTRAINT "accounts_usuario_username_key" UNIQUE (username);
ALTER TABLE "catalogos_catalogo" ADD CONSTRAINT "catalogo_clase_codigo_unico" UNIQUE (clase, codigo);
ALTER TABLE "catalogos_catalogo" ADD CONSTRAINT "catalogo_clase_valor_unico" UNIQUE (clase, valor);
ALTER TABLE "catalogos_catalogo" ADD CONSTRAINT "catalogos_catalogo_pkey" PRIMARY KEY (id);
ALTER TABLE "catalogos_proceso" ADD CONSTRAINT "catalogos_proceso_nombre_key" UNIQUE (nombre);
ALTER TABLE "catalogos_proceso" ADD CONSTRAINT "catalogos_proceso_pkey" PRIMARY KEY (id);
ALTER TABLE "django_migrations" ADD CONSTRAINT "django_migrations_pkey" PRIMARY KEY (id);
ALTER TABLE "hallazgos_accion" ADD CONSTRAINT "hallazgos_accion_codigo_key" UNIQUE (codigo);
ALTER TABLE "hallazgos_accion" ADD CONSTRAINT "hallazgos_accion_pkey" PRIMARY KEY (id);
ALTER TABLE "hallazgos_ciclotratamiento" ADD CONSTRAINT "ciclo_hallazgo_numero_unico" UNIQUE (hallazgo_id, numero);
ALTER TABLE "hallazgos_ciclotratamiento" ADD CONSTRAINT "hallazgos_ciclotratamiento_pkey" PRIMARY KEY (id);
ALTER TABLE "hallazgos_correlativosac" ADD CONSTRAINT "hallazgos_correlativosac_pkey" PRIMARY KEY (id);
ALTER TABLE "hallazgos_correlativosac" ADD CONSTRAINT "sac_anio_ambito_unico" UNIQUE (anio, ambito);
ALTER TABLE "hallazgos_hallazgo" ADD CONSTRAINT "hallazgos_hallazgo_codigo_key" UNIQUE (codigo);
ALTER TABLE "hallazgos_hallazgo" ADD CONSTRAINT "hallazgos_hallazgo_pkey" PRIMARY KEY (id);
ALTER TABLE "hallazgos_historialhallazgo" ADD CONSTRAINT "hallazgos_historialhallazgo_pkey" PRIMARY KEY (id);
ALTER TABLE "sistema_registro_auxiliar" ADD CONSTRAINT "sistema_registro_auxiliar_pk" PRIMARY KEY (tipo, clave);

ALTER TABLE "catalogos_proceso" ADD CONSTRAINT "catalogos_proceso_responsable_id_9ca91c92_fk_accounts_" FOREIGN KEY (responsable_id) REFERENCES accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_accion" ADD CONSTRAINT "hallazgos_accion_ciclo_id_2055bb12_fk_hallazgos" FOREIGN KEY (ciclo_id) REFERENCES hallazgos_ciclotratamiento(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_accion" ADD CONSTRAINT "hallazgos_accion_responsable_id_e98a4954_fk_accounts_usuario_id" FOREIGN KEY (responsable_id) REFERENCES accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_ciclotratamiento" ADD CONSTRAINT "hallazgos_ciclotrata_analisis_responsable_2d85dcfa_fk_accounts_" FOREIGN KEY (analisis_responsable_id) REFERENCES accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_ciclotratamiento" ADD CONSTRAINT "hallazgos_ciclotrata_creado_por_id_58c1e7cf_fk_accounts_" FOREIGN KEY (creado_por_id) REFERENCES accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_ciclotratamiento" ADD CONSTRAINT "hallazgos_ciclotrata_hallazgo_id_ee689a58_fk_hallazgos" FOREIGN KEY (hallazgo_id) REFERENCES hallazgos_hallazgo(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_ciclotratamiento" ADD CONSTRAINT "hallazgos_ciclotrata_responsable_cierre_i_e8a26f3e_fk_accounts_" FOREIGN KEY (responsable_cierre_id) REFERENCES accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_hallazgo" ADD CONSTRAINT "hallazgos_hallazgo_fuente_deteccion_id_9bc417fc_fk_catalogos" FOREIGN KEY (fuente_deteccion_id) REFERENCES catalogos_catalogo(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_hallazgo" ADD CONSTRAINT "hallazgos_hallazgo_prioridad_id_9335da0c_fk_catalogos" FOREIGN KEY (prioridad_id) REFERENCES catalogos_catalogo(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_hallazgo" ADD CONSTRAINT "hallazgos_hallazgo_proceso_id_8b5bdc59_fk_catalogos_proceso_id" FOREIGN KEY (proceso_id) REFERENCES catalogos_proceso(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_hallazgo" ADD CONSTRAINT "hallazgos_hallazgo_registrado_por_id_ceae8bdd_fk_accounts_" FOREIGN KEY (registrado_por_id) REFERENCES accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_hallazgo" ADD CONSTRAINT "hallazgos_hallazgo_responsable_id_1ac2c44b_fk_accounts_" FOREIGN KEY (responsable_id) REFERENCES accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_hallazgo" ADD CONSTRAINT "hallazgos_hallazgo_tipo_registro_id_25e04da9_fk_catalogos" FOREIGN KEY (tipo_registro_id) REFERENCES catalogos_catalogo(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_hallazgo" ADD CONSTRAINT "hallazgos_hallazgo_updated_by_id_3981db0c_fk_accounts_" FOREIGN KEY (updated_by_id) REFERENCES accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_hallazgo" ADD CONSTRAINT "hallazgos_hallazgo_urgencia_id_9d147ef0_fk_catalogos" FOREIGN KEY (urgencia_id) REFERENCES catalogos_catalogo(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_historialhallazgo" ADD CONSTRAINT "hallazgos_historialh_accion_relacionada_i_130b7038_fk_hallazgos" FOREIGN KEY (accion_relacionada_id) REFERENCES hallazgos_accion(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_historialhallazgo" ADD CONSTRAINT "hallazgos_historialh_hallazgo_id_0dae44b7_fk_hallazgos" FOREIGN KEY (hallazgo_id) REFERENCES hallazgos_hallazgo(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "hallazgos_historialhallazgo" ADD CONSTRAINT "hallazgos_historialh_usuario_id_26917eee_fk_accounts_" FOREIGN KEY (usuario_id) REFERENCES accounts_usuario(id) DEFERRABLE INITIALLY DEFERRED;
