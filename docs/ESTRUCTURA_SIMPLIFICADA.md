# Estructura productiva: 24 tablas físicas y 0 vistas

La base `gestion_no_conformidades` usa PostgreSQL y contiene exactamente 24 tablas físicas. La migración conserva los identificadores y datos existentes y separa los registros que antes compartían `configuracion` y `evento`.

| # | Tabla | Contenido |
|---:|---|---|
| 1 | `usuario` | Credenciales cifradas, perfil corporativo, área, cargo, jefatura y estado. |
| 2 | `usuario_rol` | Roles funcionales asignados a cada usuario. |
| 3 | `catalogo` | Tipos, fuentes, impacto, urgencia, prioridad y categorías 6M. |
| 4 | `proceso` | Procesos, gerencia, responsable y configuración compatible de validadores. |
| 5 | `proceso_validador` | Relación normalizada entre procesos y validadores. |
| 6 | `subproceso` | Subprocesos pertenecientes a cada proceso. |
| 7 | `matriz_prioridad` | Resultado de prioridad para cada combinación de impacto y urgencia. |
| 8 | `configuracion_impacto` | Rangos editables de clientes, tiempo e impacto financiero. |
| 9 | `configuracion_urgencia` | Rangos de urgencia por jefatura. |
| 10 | `pregunta_causa` | Preguntas configurables del análisis 6M. |
| 11 | `auditoria_administracion` | Cambios administrativos con valores anteriores, nuevos, actor y fecha. |
| 12 | `correlativo_sac` | Último correlativo reservado por año y ámbito. |
| 13 | `registro_general` | Expediente principal de cada hallazgo, identificación, prioridad, criticidad y estado. |
| 14 | `ciclo_tratamiento` | Planes, reaperturas, análisis 6M, respuestas, controles y datos de cierre. |
| 15 | `actividad` | Soluciones inmediatas y acciones correctivas, responsables, fechas, avance y estado. |
| 16 | `pbi` | Referencias tecnológicas PBI/Helix asociadas al ciclo. |
| 17 | `evaluacion_eficacia` | Evaluaciones de Calidad y resultado eficaz o no eficaz. |
| 18 | `comunicacion` | Constancias de comunicación del tratamiento. |
| 19 | `evidencia` | Nombre, tipo, tamaño, descripción, autor y contexto de cada evidencia. |
| 20 | `archivo_evidencia` | Contenido binario y SHA-256 del documento, dentro de PostgreSQL. |
| 21 | `historial_hallazgo` | Transiciones, seguimientos, reprogramaciones y trazabilidad funcional. |
| 22 | `notificacion` | Avisos internos y estado de lectura. |
| 23 | `django_session` | Sesiones autenticadas y su vencimiento. |
| 24 | `django_migrations` | Versiones del esquema ya instaladas. |

No se crean vistas ni vistas materializadas. `registro_general` reemplaza definitivamente cualquier nombre físico anterior de hallazgo. Las reprogramaciones y seguimientos se conservan en `historial_hallazgo` con metadatos estructurados; el análisis, las respuestas 6M, los controles y el cierre se conservan por ciclo en `ciclo_tratamiento`.

## Integridad de las evidencias

`evidencia` contiene los metadatos y la relación con el expediente, actividad, análisis, evaluación o cierre. `archivo_evidencia` contiene los bytes completos y el hash SHA-256. La descarga autenticada lee directamente la base de datos y no depende de una carpeta del servidor.

## Comprobación

```sql
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

SELECT count(*)
FROM pg_views
WHERE schemaname = 'public';
```

La primera consulta debe devolver 24 filas y la segunda, cero.

## Migración

`catalogos.0010` separa catálogos, procesos y matrices. `hallazgos.0023` separa ciclos y eventos, comprueba la cantidad de filas de cada tipo, reconstruye claves foráneas y secuencias, y elimina las dos tablas compactas solamente después de copiar y validar los datos.
