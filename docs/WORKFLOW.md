# Workflow y permisos

La interfaz sigue las cuatro etapas aprobadas. El servicio Python es la autoridad para transiciones: ocultar un botón no concede ni revoca permisos. Los campos Estado, Código SAC, actor de registro y fecha de registro no se aceptan como entradas libres. Los estados de validación antiguos permanecen solo para compatibilidad histórica y no forman parte del recorrido visible.

## Roles y alcance

| Acción | USUARIO | VALIDADOR | ADMINISTRADOR |
|---|---|---|---|
| Registrar | Con permiso registrar | Con permiso registrar adicional | Con permiso registrar adicional |
| Ver expedientes | Reportados, a cargo o con acciones asignadas | Solo procesos asignados y relaciones personales permitidas | Todos |
| Editar identificación | Reportante en borrador | En sus propios registros con permiso | No por ser administrador |
| Continuar identificación | Reportante o responsable | En sus propios registros con permiso | No existe aprobación administrativa |
| Registrar tratamiento | Responsable autorizado del caso | Proceso asignado | Solo con autorización funcional adicional |
| Actualizar acción | Responsable de acción/caso según autorización | Proceso asignado | Solo con autorización funcional adicional |
| Evaluar eficacia/cerrar | No por rol de reportante | Permiso específico y proceso asignado | Solo con autorización funcional adicional |
| Catálogos y usuarios | No | No | Permiso administrar plataforma |
| Auditoría general/reportes | Solo historia de casos visibles | Alcance asignado | Global |

La persona reportante, el responsable de proceso, el responsable del caso, el ejecutor de acción, el validador y el evaluador son conceptos independientes. PRO asigna responsabilidad de eficacia al responsable del proceso; la plataforma debe asignar permisos a quien represente esa función. Toda ampliación de acceso requiere cambio explícito de configuración y pruebas.

## Transiciones de primera versión

Cada transición registra historia y notificaciones pertinentes en la misma transacción. Para cierre y reapertura se exige motivo/observación y confirmación.

| Origen | Acción del servicio | Actor autorizado | Condiciones | Destino |
|---|---|---|---|---|
| Sin registro | crear borrador | Permiso registrar | Tipo, título, proceso y responsable mínimos; código/actor/timestamp backend | BORRADOR |
| BORRADOR | continuar identificación crítica | Reportante o responsable | Identificación completa, matriz activa y categoría crítica | EN_ANALISIS |
| BORRADOR | continuar identificación | Reportante o responsable | Identificación completa y matriz activa | EN_ANALISIS |
| ACCION_INMEDIATA | enviar_verificacion | Gestor autorizado | No crítica; inmediata completada con evidencia y comunicación | EN_VERIFICACION |
| EN_ANALISIS | iniciar_pbi | Gestor autorizado | Crítica tecnológica; análisis del ciclo completo | PBI_EN_GESTION |
| EN_ANALISIS | planificar | Gestor autorizado | Crítica no tecnológica; 6M, controles y causa completados | PLAN_ACCION |
| PBI_EN_GESTION | planificar | Gestor autorizado | Análisis completo y referencia PBI manual existente | PLAN_ACCION |
| PLAN_ACCION | iniciar_implementacion | Gestor autorizado | Al menos una correctiva con responsable, FET y resultado esperado | EN_IMPLEMENTACION |
| EN_IMPLEMENTACION | enviar_verificacion | Gestor autorizado | Acciones requeridas completadas, evidencia y comunicación; PBI cuando aplica | EN_VERIFICACION |
| EN_VERIFICACION | evaluar EFICAZ | Evaluador autorizado del proceso | Resultado, fecha, comentario y evidencia objetiva del ciclo | EN_VERIFICACION |
| EN_VERIFICACION | cerrar | Permiso cerrar y alcance | Última evaluación del ciclo EFICAZ, obligaciones cumplidas, observación/confirmación | CERRADO |
| EN_VERIFICACION | evaluar NO_EFICAZ | Evaluador autorizado | Conservar evaluación/ciclo anteriores y abrir ciclo nuevo | REABIERTO |
| CERRADO | reabrir | Permiso evaluar/cerrar y alcance | Motivo, confirmación, nuevo ciclo; no editar el cerrado | REABIERTO |
| REABIERTO | iniciar_inmediata | Gestor autorizado | Reevaluar categoría sin cambio automático; nuevo tratamiento | ACCION_INMEDIATA |
| REABIERTO | iniciar_analisis | Gestor autorizado | Sigue crítica y nueva corrección/comunicación exigibles documentadas | EN_ANALISIS |

No se permite BORRADOR → CERRADO ni estado arbitrario enviado por POST. No hay validación del administrador entre Identificación y Tratamiento. La disponibilidad de una acción debe evaluar permisos, etapa y condiciones del caso. CANCELADO no dispone de reapertura ordinaria. CERRADO solo admite la reapertura documentada y operaciones de consulta.

## Reglas de la bifurcación

- **No crítica**: completa el checklist 6M y luego continúa con corrección, comunicación, verificación y cierre. Las acciones correctivas se reservan para los casos críticos. No se acepta evaluación NA como cierre.
- **Crítica**: pasa directamente de Identificación al análisis 6M con 32 preguntas y causa raíz; después continúa con solución inmediata y correctivas. Si 4.1 indica controles existentes, completar tipos, nombre, descripción, mitigación, frecuencia, responsable y evidencia.
- **Crítica tecnológica**: requiere matriz aplicable y PBI trazable. DOC-CAT-001 está pendiente; la matriz usada localmente está marcada demo y no determina sola la criticidad. REQUIRE_CLOSED_PBI=False exige referencia, no cierre del PBI; si cambia la configuración, la condición adicional debe mostrarse al usuario.
- **No eficaz**: abre nuevo ciclo, conserva acciones/análisis/evaluación precedentes e indica reevaluación de categoría. Una no crítica no cambia automáticamente a crítica. Ninguna evaluación eficaz de un ciclo anterior habilita el cierre actual.

## Actividades dentro de una etapa

Una acción puede estar Pendiente, En proceso o Completada y conservar varios seguimientos. Reprogramar mantiene FET inicial, registra fecha anterior/nueva/motivo/actor y limita a tres por acción con bloqueo transaccional. Cancelación de acciones queda pendiente de definición; no equivale a Completada.

Registrar comunicación, adjuntar evidencia o evaluar eficaz no necesita un estado nuevo de Hallazgo. Evaluar eficaz permite una decisión posterior de cierre; registrar todas las acciones al 100 % no cierra automáticamente. El progreso mostrado se calcula desde obligaciones reales y no sustituye evaluación de eficacia.

## Integridad y concurrencia

Bloquear Hallazgo antes de modificar sus dependencias; validar versión cuando se proporcione. Releer estado bajo el bloqueo. Evitar historia/notificaciones huérfanas y rechazar la segunda solicitud si su precondición ya dejó de existir. Correlativo SAC y acción tienen restricciones únicas; reprogramación conserva unicidad por acción/número. Validaciones de backend se ejecutan también frente a URL o POST manual.

La matriz es una especificación verificable, no un certificado de que la implementación ya la satisface. La trazabilidad identifica las pruebas previstas y su estado.
