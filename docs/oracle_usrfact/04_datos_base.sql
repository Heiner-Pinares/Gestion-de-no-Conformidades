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
