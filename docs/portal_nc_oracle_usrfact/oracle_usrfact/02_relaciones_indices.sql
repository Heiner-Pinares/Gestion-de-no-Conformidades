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
-- Oracle considera duplicadas las claves compuestas (clase, NULL) cuando la
-- primera columna no es nula. El indice funcional reproduce la regla del
-- modelo: valor es unico por clase solamente cuando valor no es NULL.
CREATE UNIQUE INDEX ux_cat_clase_valor_nc
    ON tbl_catalogo_nc (
        CASE WHEN valor IS NOT NULL THEN clase END,
        CASE WHEN valor IS NOT NULL THEN valor END
    );
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
