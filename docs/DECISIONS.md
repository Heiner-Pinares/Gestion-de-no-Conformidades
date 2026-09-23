# Decisiones de arquitectura

Estado: diseño acordado para la primera implementación local. Las decisiones no constituyen evidencia de que sus pruebas hayan pasado; consultar REQUIREMENTS_TRACEABILITY.md y los resultados de ejecución.

## ADR-001 Aplicación Django modular

Usar Python 3.12, Django 5.2 LTS, PostgreSQL y templates/formularios Django. Accounts gobierna identidad/permisos, catálogos gobierna maestros y hallazgos reúne el tratamiento transaccional. Unificar acciones, causas, notificaciones e historial dentro del dominio reduce acoplamiento inicial sin convertir cada tabla en una app.

## ADR-002 PostgreSQL como persistencia real

No usar SQLite como base principal. Configuración por entorno, migraciones Django y semillas idempotentes. La instancia de desarrollo debe ser aislada; el código no depende de pgAdmin ni de una ruta personal. Secuencias, unicidad, referencias y restricciones simples protegen integridad además de validación Python.

## ADR-003 Interfaz derivada del HTML v8

Conservar CSS, paleta Claro, SVG telecom, login, cards, tablas, badges y progresión por etapas. Dividir en templates con includes. Sustituir navegación por ocultamiento del DOM por rutas autorizadas. Usar POST/GET y details/summary; validaciones y cálculos definitivos permanecen en Python. Los mensajes de guardado corresponden a transacciones reales.

## ADR-004 Usuario propio y permisos combinables

Custom User desde primera migración con corporate_identifier opcional, grupos y permisos funcionales. USUARIO, VALIDADOR y ADMINISTRADOR son combinables. El permiso global no sustituye el alcance del objeto: filtrar QuerySets y comprobar autor, responsable, acción asignada, proceso y estado. Administrador funcional se diferencia del superusuario técnico. Autovalidación se prohíbe también en cuentas con varios roles.

## ADR-005 Servicios explícitos y transacciones

Views coordinan HTTP, Forms validan entrada, Services implementan casos de uso y Selectors concentran consultas. WorkflowService utiliza matriz cerrada. Bloquear primero Hallazgo antes de sus dependencias y comprobar estado/versión evita doble validación, códigos repetidos y cuarta reprogramación concurrente. Estado, historial y notificaciones internas se escriben dentro de la misma transacción.

## ADR-006 Ciclos de tratamiento

Hallazgo 1:N CicloTratamiento, un análisis por ciclo, varias acciones/PBI/evaluaciones por ciclo. No eficaz crea un nuevo ciclo; cierre conserva referencia al ciclo evaluado. Esta estructura permite reapertura sin reemplazar causas ni dar validez a una evaluación anterior. La categoría no cambia automáticamente al reabrir.

## ADR-007 Acciones normalizadas y fechas históricas

Una entidad Accion con tipo INMEDIATA/CORRECTIVA mantiene naturaleza distinta mediante permisos, etapas y validaciones. Acción 1:N SeguimientoAccion y ReprogramacionAccion. Código correlativo por hallazgo, FET inicial inmutable, fecha vigente derivada de última reprogramación. La cancelación no se usa como atajo para satisfacer cierre.

## ADR-008 Políticas calculadas y snapshots

MAX de tres impactos es una política provisional centralizada. MatrizPrioridad es configurable y distingue demo de oficial. Guardar resultado/snapshot aplicado permite interpretar decisiones pasadas tras cambios de catálogo. Prioridad operativa y clasificación crítica de NC son campos diferentes. Registrar sustento de categoría y requisito de referencia.

## ADR-009 Evidencias privadas

Guardar archivo con nombre físico aleatorio, tipo/tamaño validados y nombre original como metadato. Evidencia pertenece al hallazgo y como máximo a un contexto compatible. Descargar mediante vista autenticada con alcance del caso, sin exponer MEDIA_ROOT como sitio público. La evidencia en una acción/ciclo diferente no acredita automáticamente el tratamiento actual.

## ADR-010 Historial funcional separado de logs

HistorialHallazgo es append-only en operación ordinaria, con actor, timestamp, transición, motivo y metadatos. Logs Python describen errores técnicos sin secretos ni contenido innecesario. Proteger usuarios y catálogos referenciados mediante PROTECT/inactivación, no borrado en cascada sobre expedientes.

## ADR-011 Comunicación y notificación separadas

ComunicacionHallazgo acredita el paso formal de comunicación con registro manual. Notificacion informa al usuario dentro del portal. No se añaden correo, WhatsApp, Teams, LDAP, Entra ID, Remedy ni Helix externos. PBI conserva referencias manuales; REQUIRE_CLOSED_PBI es configurable y falso por defecto porque la fuente formal no lo exige.

## ADR-012 Configuración frente a semilla demo

Semilla inicial idempotente para roles, maestros y 32 preguntas; semilla demo separada para usuarios y casos. No insertar automáticamente demostraciones en producción. La matriz no oficial debe conservar marca demo incluso si se incluye como configuración inicial de desarrollo.

## ADR-013 Evidencia de aceptación

Pruebas de escenarios sobre PostgreSQL real, controles negativos de permisos, invariantes de cierre/reapertura y límites de reprogramación. No afirmar conformidad productiva a partir de «la página carga». Revisar además fidelidad visual, responsive y uso sin JavaScript de negocio.
