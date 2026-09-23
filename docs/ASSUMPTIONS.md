# Supuestos y reglas pendientes

Estos supuestos permiten desarrollar y probar localmente sin presentar decisiones provisionales como políticas oficiales. La ausencia de DOC-CAT-001 y de la matriz de comunicación impide certificar la operación productiva; no impide construir un prototipo con configuración identificada como demo.

| ID | Decisión de primera versión | Origen y pendiente | Consecuencia y reversibilidad |
|---|---|---|---|
| A-001 | Correlativo SAC por tipo y año, `SAC_SEQUENCE_SCOPE=TYPE`. | TEC §29 propone unicidad por tipo/año, §28 muestra secuencia global; CRIT §12 exige explicitar la ambigüedad. | Se puede configurar `YEAR`; cambiar con datos existentes exige continuidad y revisión de colisiones. Nunca regenerar códigos históricos. |
| A-002 | Impacto resultante = máximo de clientes, tiempo y soles. | TEC §33; CRIT §14 lo identifica como provisional. | Política centralizada, reemplazable. No se definen umbrales numéricos inventados. |
| A-003 | Matriz de nueve combinaciones tomada del HTML con `es_demo=True`. | Falta DOC-CAT-001 requerido por PRO, actividad 1 y Anexo 2. | Mostrar condición demo; cálculo de prioridad no convierte automáticamente una NC en crítica. Falta combinación activa → error, sin valor por defecto. |
| A-004 | Criticidad SI/NO debe constar antes del envío; conservar opción NA en borrador. | FOR permite NA, PRO solo dirige dos rutas NC. | Evita usar NA para saltar controles. Pendiente alcance de NA para registros que no constituyen NC. |
| A-005 | USUARIO ve casos reportados, bajo su responsabilidad o con acción asignada; edición depende de relación y etapa. | CRIT §11 declara alcance pendiente. | Política explícita y restrictiva; asignación de una acción no concede decisión sobre todo el expediente. |
| A-006 | VALIDADOR actúa solo en procesos asignados y nunca valida su propio registro. | TEC §§13, 15; PRO tabla de responsabilidades. | Las asignaciones son datos modificables. El perfil Calidad no da competencia sobre cualquier proceso. |
| A-007 | Administrador consulta todos y administra; no recibe automáticamente validación, tratamiento, eficacia ni cierre. | TEC §17 y CRIT §§9, 75. | Una persona puede acumular grupos; se suman permisos sin duplicar usuarios. |
| A-008 | Tipo NOC usa etiqueta exacta «No Conforme» y reconoce alias documental «No Conformidad». | TEC §§26, 74 frente a FOR Formato!C5:G5. | Mantiene etiqueta explícita solicitada para plataforma; no modifica documentos oficiales. Código permanece NOC. |
| A-009 | Mantener las nueve fuentes exactas; «Proveedor externo» se registra como Otro con detalle justificado. | TEC §27 frente a PRO Anexo 1. | Catálogo puede ampliarse tras definición; no descartar casos de proveedor ni equiparar toda fuente con NC. |
| A-010 | Fecha de solución representa compromiso previsto; la fecha real corresponde a ejecución/cierre. Validar hoy/futuro al crear o modificar compromiso. | TEC §31 frente a FOR Formato!A13, que no distingue prevista/real. | Una fecha ya vencida no debe impedir corregir otros datos ni perderse por edición. Pendiente aclaración de etiqueta definitiva. |
| A-011 | Impacto puede declararse no aplicable en origen no tecnológico con sustento. Para tecnológico se exige evaluación y urgencia. | FOR Formato!A14:A16; PRO Anexo 2. | Evita inventar impactos financieros/técnicos. Conservar criterio de categorización separado. |
| A-012 | Máximo tres reprogramaciones por acción; fecha inicial inmutable. | TEC §§45–46 y CRIT §59. No consta en PRO. | Regla temporal protegida en servicio/transacción. Pendiente autoridad de aprobación y condiciones de anticipación/postergación. |
| A-013 | Comunicación es constancia manual con destinatarios, canal, resumen, fecha y actor. | PRO actividad 4; dos gráficos citan Anexo 3 y GFAC-MAT-005. | No se envían correos/WhatsApp/Teams. Una notificación interna no sustituye evidencia de comunicación operativa. |
| A-014 | Todo resultado no eficaz abre nuevo ciclo sin borrar el anterior. Una no crítica mantiene categoría y requiere reevaluación explícita. | PRO compuerta final y Anexo 2. | No convertir a crítica silenciosamente. Debe existir ruta de nueva corrección y posibilidad de escalar con sustento. |
| A-015 | Reapertura manual de cerrado exige permiso de evaluación/cierre, motivo, confirmación e historial. | TEC incluye reapertura; PRO describe principalmente retorno por no eficaz. | Extensión de plataforma, distinta de reapertura automática por no eficaz. No permite editar el ciclo cerrado. |
| A-016 | Para crítica tecnológica se exige referencia PBI; `REQUIRE_CLOSED_PBI=False` de inicio. | PRO requiere gestión y trazabilidad, no establece que PBI deba estar cerrado para verificar. | Una política posterior puede exigir cierre de PBI sin modificar relaciones ni historia. Integración Helix/Remedy permanece manual. |
| A-017 | PBI pertenece a un ciclo; un caso puede tener varios y un número puede estar relacionado con varios casos. | CRIT §22 pide analizar cardinalidad. | No declarar número globalmente único sin confirmación; documentar vínculos al incidente. |
| A-018 | Acciones operativas usan Pendiente, En proceso y Completada. Cancelación no está habilitada hasta definir autorización y efecto en cumplimiento. | FOR/MAT añaden Cancelado y nombran Terminado al estado final. | Diferencia visible documentada; no simular cancelaciones como completadas. Se puede cambiar etiqueta Completada/Terminado sin perder datos. |
| A-019 | Cerrar exige evaluación EFICAZ del ciclo actual, incluso para no críticas. | PRO Riesgos y controles, actividad 9; FOR/MAT permiten resultado NA. | NA no se considera autorización de cierre de NC. Pendiente semántica de NA para registros fuera de alcance. |
| A-020 | Caso vencido: compromiso de solución anterior a hoy local, excluyendo cerrado y cancelado. | CRIT §§53–54 exige definición formal. | Métrica provisional declarada; las fechas vigentes de acciones se muestran separadas. «Por vencer» se mostrará solo con ventana explícita. |
| A-021 | El cálculo HTML 100 menos 20 por reprogramación no se usa como eficacia oficial. | HTML `score()`; ausente de PRO/FOR/MAT y criticado por CRIT §53. | Preservar histórico de fechas y número de reprogramaciones. Eficacia deriva de evaluación documentada, no de puntuación demo. |
| A-022 | El tipo no cambia después de generar SAC. | Código incluye tipo; TEC exige código generado único; CRIT pide trazabilidad. | Para error de tipo se requiere devolución/cancelación con nuevo registro relacionado o futura operación de reclasificación. No renumerar silenciosamente. |
| A-023 | Los trece estados se conservan; códigos estructurales no son editables por catálogo ordinario. | TEC §21; CRIT §§6–7. | Se administran etiquetas/catalogación bajo control, pero una etiqueta nueva no crea una transición válida. |
| A-024 | Un análisis por ciclo y múltiples ciclos por hallazgo. Respuestas conservan texto/código de pregunta utilizados. | CRIT §§19–21, 69. | Evita pérdida de historia cuando se reabre o cambian preguntas. |

## Confirmaciones necesarias antes de producción

1. Incorporar DOC-CAT-001, aprobar umbrales y matriz, y decidir cómo fundamentar criticidad tecnológica.
2. Aprobar alcance de acceso, asignaciones de validadores y delegación de responsables del proceso.
3. Resolver semántica NA, no eficaz en no críticas, cancelación de acciones/casos y reapertura manual de cerrados.
4. Confirmar tipo/alias NOC, fuente de proveedor, correlativo y edición excepcional del tipo.
5. Confirmar política de reprogramaciones, vencimiento, métricas y retención de evidencias.
6. Determinar la versión vigente del gráfico de comunicación y facilitar GFAC-MAT-005 si corresponde.

Estos puntos son validaciones del negocio para adopción operacional. Ninguno autoriza enviar mensajes ni crear integraciones externas durante el desarrollo.
