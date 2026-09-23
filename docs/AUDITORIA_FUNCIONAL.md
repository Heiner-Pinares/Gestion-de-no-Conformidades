# Auditoría funcional de las fuentes del proceso

Revisión de los dos prompts adjuntos y de tres documentos formales. Los archivos originales no se modificaron. El HTML fue revisado por el agente principal; las referencias a su comportamiento en este informe provienen de esa revisión coordinada.

## Fuentes y alcance

- **PRO**: `GPP-PRO-004 Procedimiento de Gestión de No Conformidades.docx`, versión 6.0 del 27/08/2026. Se leyó todo el texto y las dos imágenes del flujo incluidas en la sección Descripción. El flujo no está disponible como texto OOXML.
- **FOR**: `GPP-FOR-004 Solicitud de acción correctiva.xlsx`, versión 04 del 27/08/2026. Hojas Formato, Causa Raiz y Control de Cambios.
- **MAT**: `GPP-MAT-00X Matriz Control Hallazgos.xlsx`, versión 1.0 del 27/08/2026. Hojas Hallazgos, Hoja1 y Control de Cambios.
- **CRIT**: prompt «Contexto de razonamiento crítico y criterio de ingeniería», 100 secciones.
- **TEC**: prompt «Actúa como un arquitecto de software senior…», 94 secciones.

La jerarquía solicitada en CRIT §2 prioriza documentos formales, requerimientos posteriores, decisiones aprobadas, HTML, datos demo e inferencias. Un ejemplo o una validación heredada de Excel no adquiere automáticamente carácter de regla aprobada.

## Reglas formales que debe proteger el backend

1. Identificar un origen no basta para afirmar que existe una NC: verificar incumplimiento de un requisito o necesidad de tratamiento según criterios aplicables. PRO, Anexo 1, párrafo inicial.
2. Categorizar como crítica/no crítica en la actividad 1. La compuerta posterior solo dirige el tratamiento; no es una segunda clasificación. Guardar fuente y criterio que sustenta categoría. PRO, Lineamientos y Descripción, actividad 1.
3. El responsable del proceso valida la categoría, asegura corrección y comunicación, dirige análisis y acciones, y verifica eficacia. Calidad brinda soporte metodológico, trazabilidad, seguimiento y consolidación. El permiso Validador puede representar al responsable del proceso conforme a TEC §15; asignarlo a una persona no implica que cualquier miembro de Calidad tenga competencia sobre cualquier proceso. PRO, tabla de responsabilidades.
4. Registrar fuente, descripción, proceso/servicio afectado, responsable, fechas aplicables, impacto/urgencia/prioridad cuando corresponda, evidencia disponible y referencia tecnológica si aplica. PRO, actividad 2.
5. Registrar corrección/acción inmediata, responsable, fecha y evidencia. Distinguir corrección de acción correctiva. PRO, actividad 3; FOR, Formato!A21:G27.
6. Comunicar corrección implementada, estado y restauración cuando corresponda. Para críticas, incluir información mínima de la organización. PRO, actividad 4 y Anexo 3; existe una discrepancia documental sobre la referencia de comunicación descrita más abajo.
7. No crítica: corrección + comunicación + verificación + cierre. No exigir 6M ni AC. Nunca marcar la verificación como innecesaria. PRO, Lineamientos y Anexo 2.
8. Crítica: además, 6M + acciones correctivas + evaluación de eficacia. Deben ser proporcionales a efectos reales/potenciales y sustentadas en evidencia objetiva. PRO, Lineamientos, Anexo 2 y actividades 5, 7–9.
9. Crítica tecnológica: aplicar DOC-CAT-001 y gestionar PBI en Helix, preservando vínculo con incidente y NC. PRO, Anexo 2 y actividad 6. No se proporcionó DOC-CAT-001, por lo que la matriz demo no debe presentarse como oficial.
10. Una acción correctiva requiere responsable, FET y evidencia de cumplimiento asociada a causas identificadas. Su implementación necesita seguimiento y conservación de evidencia. PRO, actividades 7–8.
11. El responsable del proceso evalúa mediante evidencia objetiva si corrección/AC lograron resultado esperado y previenen recurrencia. 100 % de avance no demuestra eficacia por sí mismo. PRO, actividad 9; TEC §48.
12. Tratamiento eficaz habilita cierre. No eficaz exige revisar causas y nuevas acciones. La no crítica con recurrencia o tratamiento insuficiente se reevalúa y se trata como crítica cuando corresponda. PRO, compuerta final, Riesgos y controles, Anexo 2.
13. FOR es registro principal. MAT consolida seguimiento e incluye requisito de referencia, proceso/subproceso, responsable de proceso, evidencia, avance, verificador y fecha de cierre. PRO, Lineamientos; MAT, Hallazgos!A5:AE5.
14. Mantener las 32 preguntas 6M. En Medición, una respuesta afirmativa a existencia de controles requiere tipo, nombre, descripción, mitigación, frecuencia, responsable y evidencia. FOR, Causa Raiz!B8:B51 y B28:H34; TEC §§37–39.

## Contradicciones y defectos detectados

| Hallazgo | Fuente | Decisión propuesta e impacto |
|---|---|---|
| Tipo «No Conformidad» frente a «No Conforme» | FOR validación Formato!C5:G5 frente a TEC §§26, 74 | Conservar código NOC y usar nombre documental «No Conformidad», dejando registrada la discrepancia. Solo afecta etiqueta de catálogo; reversible. |
| Matriz ofrece «Aspecto Mejora» pero registro no lo incluye | MAT validación Hallazgos!F6:F12 frente a FOR/TEC | No crear un quinto tipo sin definición. Conservar dato de origen en futura importación y clasificarlo en revisión. No todas las oportunidades son NC. |
| Fuente Proveedor externo no figura en nueve fuentes del prompt | PRO Anexo 1 frente a TEC §27 | Prototipo puede usar «Otro» con detalle de proveedor. La cobertura definitiva requiere confirmar catálogo ampliado; no eliminar las fuentes solicitadas. |
| «Puede requerir PBI» frente a obligación de PBI | TEC §24 frente a PRO Lineamientos/Anexo 2 | Para crítica tecnológica bloquear avance a plan sin referencia PBI. La integración permanece manual, como solicitan TEC §50 y CRIT §56. |
| Impacto/urgencia/prioridad obligatorios universalmente generarían datos ficticios | FOR Formato!A14:A16 y MAT Hallazgos!N5:P5 dicen «si aplica» | Permitir no aplicabilidad justificada para origen no tecnológico; toda crítica tecnológica exige datos para matriz. La prioridad y la criticidad siguen separadas. |
| Categorizar después de validar frente a categorizar inicialmente | TEC §5 frente a PRO Lineamientos y actividad 1 | Capturar clasificación inicial y sustento en identificación; Validador confirma o corrige con auditoría. No reclasificar al pasar compuerta. |
| Correlativo anual global en ejemplos frente a unicidad por tipo/año | TEC §§28–29; CRIT §12 reconoce ambigüedad | Adoptar por tipo/año, como modelo propuesto explícitamente, con política configurable y auditoría. Nunca regenerar códigos históricos al cambiar configuración. |
| La fecha de solución del formulario puede interpretarse como fecha real, pero regla técnica exige hoy o futura | FOR Formato!A13; TEC §31 | Tratarla como fecha comprometida de solución en primera versión y separar fecha real de ejecución/cierre. Validar al crear o cambiar compromiso, no impedir editar una descripción mañana porque el compromiso quedó vencido. |
| No eficaz en no crítica vuelve a análisis en gráfico, pero Anexo 2 condiciona escalamiento | PRO compuerta final frente a Anexo 2, no crítica | REABIERTO debe exigir reevaluación explícita de categoría. Evitar conversión automática a crítica. Si continúa no crítica, justificar y renovar corrección; si pasa a crítica, abrir nuevo ciclo de análisis. Regla operacional pendiente de confirmar. |
| Cancelación y «No corresponde» no tienen tratamiento formal completo | TEC §§15, 21 y CRIT §34 | Mantener CANCELADO, restringir inicialmente a revisión inicial con motivo y auditoría. Cancelación durante tratamiento y reapertura desde cerrado requieren regla explícita. |
| FOR contiene fórmula externa equivocada | FOR Causa Raiz!C4: `IF([1]Formato!C6="","",[1]Formato!C6)` | No trasladar vínculo externo: además apunta a fuente de detección, aunque la etiqueta es «No Conformidad». En aplicación vincular directamente al hallazgo. |
| Validaciones de la matriz desplazadas | MAT Hallazgos!E13:E978 ofrece NC Mayor/Menor/Observación/OM en Fuente; P13:P978 ofrece estados en Prioridad | No importar como catálogo vigente. Usar títulos y filas 6–12 junto al procedimiento. Registrar como defecto de plantilla. |
| Dos variantes del flujo en el DOCX | PRO sección Descripción, dos imágenes | Una remite a Anexo 3 y otra a GFAC-MAT-005 para comunicación; la segunda añade MAT al seguimiento. Conservar requerimiento común y registrar falta de GFAC-MAT-005. No afirmar cuál variante está aprobada. |
| El estado «No eficaz» aislado en matriz no representa un caso real completo | MAT Hallazgos!AB6; resto fila vacío | No sembrarlo como hallazgo ni usarlo como evidencia de regla adicional. |

## Reglas pendientes y supuestos reversibles

- **Matriz oficial de impacto/urgencia y umbrales**: falta DOC-CAT-001. MAX y nueve combinaciones demo son provisionales; identificarlas en interfaz y separar configuración demo de maestra. No inventar cantidades de clientes, soles u horas.
- **Alcance de acceso**: USUARIO ve creados, a su cargo y casos que contienen acciones asignadas; esta combinación es propuesta, no regla formal. Para una acción asignada no conceder edición de toda la NC. VALIDADOR solo procesos asignados. Administrador ve todos y gobierna, pero necesita permiso de Validador para decisiones del proceso.
- **Categoría No aplica**: FOR permite Sí/No/No aplica pero PRO solo crítica/no crítica para NC. No permitir que NA evite clasificación de una NC enviada. Mantener en borradores o registros que aún no corresponden a NC hasta definición.
- **Comunicación formal**: guardar canal, fecha, responsable, resumen y evidencia/referencia. Notificaciones internas y comunicación operativa son registros diferentes.
- **Reapertura de cerrado**: no está establecida; por defecto permitir reapertura por resultado no eficaz en verificación. Mantener el estado REABIERTO, pero no habilitar arbitrariamente CERRADO → REABIERTO.
- **Reprogramaciones**: límite 3 proviene del requerimiento técnico y es temporal, no del procedimiento. Aplicar transacción y bloqueo por acción; conservar FET inicial. Pendientes: autoridad que aprueba y si nueva fecha puede anticipar anterior.
- **Estados de acciones**: FOR/MAT comparten Pendiente, En proceso, Terminado, Cancelado. Cancelada no debe computar automáticamente como implementada ni satisfacer cierre; sustitución/justificación requiere validación.
- **Vencimiento**: provisionalmente acción activa con fecha vigente anterior a fecha local; próxima a vencer requiere ventana explícita. No mezclar fecha de solución, FET y evaluación.
- **Evaluación**: FOR/MAT admiten No aplica; PRO exige verificación objetiva antes del cierre de NC. Reservar NA para registros fuera del alcance hasta definición. No cerrar una NC por evaluación NA.
- **PBI**: 0..N referencias por hallazgo satisface flexibilidad inicial. Permitir repetir un número PBI entre hallazgos si corresponde al mismo problema; no inventar unicidad global que impida relación compartida.
- **Evidencias**: definir tipos/tamaño/retención; descarga protegida por permisos de caso. Separar evidencias de cada ciclo para que la evaluación actual no utilice accidentalmente evidencia obsoleta.
- **Métricas**: porcentaje de eficacia requiere denominador y ventana temporal definidos. Evitar indicador decorativo con semántica inventada.

## Matriz propuesta de transiciones

«Responsable» significa responsable autorizado del caso/proceso, no cualquier miembro de un grupo. Cada transición debe registrar actor, timestamp, origen, destino, motivo/datos relevantes y notificación en la misma transacción. Las condiciones son requisitos verificables en Python, además de la validación de formularios.

| Origen | Acción | Actor | Condiciones principales | Destino |
|---|---|---|---|---|
| Sin registro | Guardar borrador | USUARIO autorizado | Campos mínimos de borrador y propietario asignado por backend | BORRADOR |
| BORRADOR / DEVUELTO | Enviar | Reportante | Identificación completa, responsable/proceso activo, categoría y criterio, datos aplicables válidos | PENDIENTE_VALIDACION |
| PENDIENTE_VALIDACION | Devolver | VALIDADOR del proceso | No es reportante; motivo obligatorio | DEVUELTO |
| PENDIENTE_VALIDACION | No corresponde | VALIDADOR del proceso | No es reportante; motivo y confirmación | CANCELADO |
| PENDIENTE_VALIDACION | Validar | VALIDADOR del proceso | No es reportante; confirmar datos, categoría/criterio; matriz disponible cuando aplica | VALIDADO |
| VALIDADO | Iniciar corrección | Responsable | Ciclo abierto, persona autorizada | ACCION_INMEDIATA |
| ACCION_INMEDIATA | Iniciar análisis | Responsable / VALIDADOR | Crítica; corrección implementada con evidencia y comunicación registrada | EN_ANALISIS |
| ACCION_INMEDIATA | Enviar a verificación | Responsable / VALIDADOR | No crítica; corrección implementada con evidencia y comunicación registrada | EN_VERIFICACION |
| EN_ANALISIS | Gestionar PBI | Responsable / VALIDADOR | Crítica tecnológica; 6M completo, causa identificada y controles completos cuando aplica | PBI_EN_GESTION |
| EN_ANALISIS | Preparar plan | Responsable / VALIDADOR | Crítica no tecnológica; 6M completo y causa identificada | PLAN_ACCION |
| PBI_EN_GESTION | Preparar plan | Responsable / VALIDADOR | PBI registrado, referencia a incidente/caso y responsable TI | PLAN_ACCION |
| PLAN_ACCION | Iniciar implementación | Responsable / VALIDADOR | Al menos una AC vigente con responsable, FET, resultado esperado y vínculo a ciclo/causa | EN_IMPLEMENTACION |
| EN_IMPLEMENTACION | Enviar a verificación | Responsable / VALIDADOR | Todas las AC requeridas terminadas, evidencia y fechas reales; cancelaciones justificadas no ocultan obligaciones | EN_VERIFICACION |
| EN_VERIFICACION | Registrar eficaz | VALIDADOR/evaluador del proceso | Evidencia objetiva, resultado y comentario; evaluación del ciclo actual | EN_VERIFICACION |
| EN_VERIFICACION | Cerrar | VALIDADOR autorizado | Última evaluación del ciclo eficaz, sin obligaciones pendientes, confirmación y observación | CERRADO |
| EN_VERIFICACION | Registrar no eficaz | VALIDADOR/evaluador | Resultado, evidencia y motivo; cerrar evaluación anterior y abrir ciclo de tratamiento nuevo | REABIERTO |
| REABIERTO | Reiniciar análisis | Responsable / VALIDADOR | Crítica mantenida o reclasificación explícita sustentada a crítica; preservar ciclo previo | EN_ANALISIS |
| REABIERTO | Renovar corrección | Responsable / VALIDADOR | No crítica tras reevaluación explícita justificada; regla provisional a confirmar | ACCION_INMEDIATA |

CERRADO y CANCELADO son terminales en la primera versión. No permitir salto BORRADOR → CERRADO ni editar el estado mediante formularios generales. VALIDADO y ACCION_INMEDIATA pueden resultar breves, pero se conservan porque forman parte de los trece estados solicitados. No se introducen estados adicionales para comunicación o evaluación eficaz: son actividades documentadas dentro de la etapa.

## Modelo mínimo derivado de la revisión

- Hallazgo diferencia reportante, responsable, proceso/subproceso, clasificador/validador, categoría con sustento y prioridad operativa con referencia/snapshot de política aplicada.
- CicloTratamiento 1:N conserva reanálisis, AC y evaluaciones sin sobrescribir historia. Cierre corresponde a un evento y a un ciclo.
- Acciones 1:N, con clase inmediata/correctiva y servicios específicos o entidades separadas, historial de seguimiento y reprogramaciones por acción.
- Análisis y evaluación 1:N por hallazgo, asociados a ciclo. Preguntas 6M parametrizadas con textos/versiones preservados para respuestas históricas.
- ComunicaciónTratamiento registra paso formal 4; Notificación es una entidad independiente.
- Evidencia apunta a caso y como máximo un contexto específico compatible —acción, análisis, evaluación o cierre—; validar pertenencia al mismo caso/ciclo.
- Catálogos desactivables, usuarios protegidos de eliminación, historial inmutable en operación ordinaria, código SAC único y secuencia protegida por PostgreSQL.

## Pruebas de negocio que aportan mayor cobertura

1. No crítica llega a cierre con corrección, comunicación, evidencia y evaluación eficaz; 6M/AC muestran No aplica.
2. No crítica no puede cerrar sin verificación aunque tenga acción al 100 %.
3. Crítica no tecnológica no pasa de análisis sin 32 respuestas, causa y controles requeridos.
4. Crítica tecnológica no entra en plan sin PBI, y no acepta matriz faltante con valor silencioso.
5. No eficaz conserva ciclo anterior, abre ciclo nuevo y no usa una evaluación eficaz antigua para cerrar.
6. Usuario multirrol no valida su propio caso; validador ajeno al proceso no puede leer/decidir; administrador sin rol funcional no valida.
7. Cuarta reprogramación rechazada incluso con llamadas simultáneas, sin alterar FET inicial ni historial.
8. Dos envíos/validaciones concurrentes no duplican eventos, acciones ni códigos SAC.
9. Edición de descripción con compromiso vencido conserva fecha histórica; cambiarla a una nueva fecha pasada falla.
10. Descarga de evidencia de caso ajeno falla; MIME/extensión/nombre y tamaño no se confían al navegador.
