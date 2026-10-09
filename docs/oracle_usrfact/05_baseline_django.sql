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
