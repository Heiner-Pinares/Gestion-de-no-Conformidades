# Análisis del proyecto y fuentes del proceso

Revisión de los dos prompts adjuntos y de tres documentos formales. Los archivos originales no se modificaron. El HTML v8 fue leído por el agente principal y su lógica fue revisada también durante esta auditoría.

## Fuentes y alcance

- **PRO**: `GPP-PRO-004 Procedimiento de Gestión de No Conformidades.docx`, versión 6.0 del 27/08/2026. Se leyó todo el texto y las dos imágenes del flujo incluidas en la sección Descripción. El flujo no está disponible como texto OOXML.
- **FOR**: `GPP-FOR-004 Solicitud de acción correctiva.xlsx`, versión 04 del 27/08/2026. Hojas Formato, Causa Raiz y Control de Cambios.
- **MAT**: `GPP-MAT-00X Matriz Control Hallazgos.xlsx`, versión 1.0 del 27/08/2026. Hojas Hallazgos, Hoja1 y Control de Cambios.
- **CRIT**: prompt «Contexto de razonamiento crítico y criterio de ingeniería», 100 secciones.
- **TEC**: prompt «Actúa como un arquitecto de software senior…», 94 secciones.

La jerarquía solicitada en CRIT §2 prioriza documentos formales, requerimientos posteriores, decisiones aprobadas, HTML, datos demo e inferencias. Un ejemplo o una validación heredada de Excel no adquiere automáticamente carácter de regla aprobada.

## Arquitectura y funcionalidades del HTML actual

El archivo v8 es un prototipo de una sola página con CSS, SVG inline y JavaScript propio. No contiene servidor, autenticación real ni base de datos. `showScreen()` oculta/muestra ocho elementos main en el mismo documento. La vista de login no comprueba usuario ni contraseña: `login()` muestra el panel directamente.

| Pantalla | Contenido existente | Migración prevista |
|---|---|---|
| login | Identidad Claro, ciudad/torre telecom, formulario | Django Authentication y template visual derivado |
| dashboard | Bienvenida, cards, casos recientes y accesos | Indicadores y casos del alcance personal/rol |
| registro | Identificación, matriz impacto, prioridad y criticidad | Form y servicios de creación, borrador y envío |
| causa | 32 preguntas 6M y campos de controles | Preguntas parametrizadas, respuestas/ciclo y validaciones Python |
| registro-ingresado | Constructor de acciones | Formularios por acción, persistencia 1:N y código backend |
| guardado | Confirmación y resumen de acciones | Mensaje posterior a transacción y detalle real |
| actividades | Avance, FET, tres reprogramaciones, fecha real y estado | Seguimientos/reprogramaciones históricas por acción |
| evaluacion | Resumen y evaluación/cierre conceptual | Evaluación autorizada con evidencia y cierre separado |

Hay además modales de impacto y reprogramación y mensajes temporales tipo toast. Las pantallas todavía no distinguen Usuario, Validador y Administrador ni incluyen una bandeja real de validación. Búsqueda, gobierno de usuarios/catalogación y reportes deben convertirse en rutas reales.

## JavaScript, simulaciones y persistencia actual

- `nextSequence()`, `buildCaseCode()`, `reserveCaseCode()` y `updateCaseCodePreview()` construyen SAC con fecha del navegador. Solo se persiste `sacSequence-<año>` en localStorage: contador global anual por navegador, sin coordinación entre usuarios. El código de caso puede modificarse en la previsualización al cambiar el tipo.
- `getImpactResult()` utiliza MAX de Bajo/Medio/Alto en tres dimensiones; `calculatePriority()` contiene nueve combinaciones hardcodeadas. El propio texto de UI indica parametrización futura.
- `continueFromStep1()` exige impacto/urgencia aunque sus etiquetas dicen «si aplica», y trata NA como ruta no crítica. Esta ambigüedad no debe trasladarse a backend.
- `completeChecklist()` comprueba las 32 respuestas y los campos de control si 4.1=Sí. `toggleControlDetails()` solo cambia opacidad; no es una autorización ni validación de servidor.
- `activities` es un array en memoria. `saveActivities()` sustituye la lista y crea reprogramaciones vacías; reconstruirla puede perder el historial anterior. Nombres y responsables vacíos se convierten en «Actividad sin descripción»/«Sin asignar» en vez de rechazarse.
- `renderStep3()` propone acción inmediata y correctiva incluso cuando el caso no es crítico. La nueva versión debe respetar aplicabilidad del proceso.
- `setState()` y `setReal()` modifican datos en memoria sin transición, historial ni autorización. `confirmReprogram()` agrega una fecha y no conserva actor/motivo.
- `score()` calcula 100 menos 20 por reprogramación; `renderStep4()` promedia esa «eficiencia». Ningún documento formal suministrado define ese indicador. No se equipara a eficacia del tratamiento.
- Bienvenida, nombres, casos y métricas del panel son datos de demostración. No son maestros ni deben aparecer como expedientes productivos. No hay integración Remedy/Helix/SSO ni envío real de notificaciones.

Toda generación de códigos, cálculo definitivo, validación, transición, permiso y persistencia migra a Python. Solo presentación/expansión nativa permanece en HTML/CSS.

## Riesgos técnicos, funcionales y de seguridad

| Área | Evidencia y riesgo | Medida prevista |
|---|---|---|
| Identidad | Login no autentica y navegación no controla sesión | Custom User, Authentication, sesión y logout POST |
| Autorización | UI única, IDs o botones pueden manipularse | Permisos de backend más alcance del objeto y proceso |
| Concurrencia | Contador localStorage y estado en navegador | PostgreSQL, unicidad, atomicidad y bloqueo |
| XSS | Valores de acciones se insertan en `innerHTML` sin escape | Autoescape Django y ausencia de HTML confiado del usuario |
| Historia | Guardado sustituye array y reinicia reprogramaciones | Entidades 1:N e historial append-only |
| Fechas | Reloj del navegador y campos date para auditoría | Timestamps backend, USE_TZ y America/Lima |
| Cierre | Resumen de avance/eficiencia no prueba eficacia | Evaluación objetiva del ciclo actual y cierre autorizado |
| Evidencias | Sin control real de subida/descarga | Validación de contenido/tamaño y rutas privadas |
| Datos demo | Cifras y reglas de demostración aparentan definitivas | Semilla separada, marca demo y supuestos declarados |
| Producción | No hay política de despliegue/secretos/logs | Configuración por entorno, logs controlados y modo desarrollo explícito |

## UX a conservar y mejorar

Conservar paleta rojo Claro (#E30613), fondos claros, bordes suaves, login dividido, SVG isométrico telecom, tarjetas, badges, tablas, stepper y preguntas 6M. Extraer el CSS y las ilustraciones sin sustituirlos por un diseño genérico. Las mejoras justificadas son navegación por rol, progressive disclosure, details/summary nativos, formularios por etapa, mensajes reales, estados vacíos, labels/foco y feedback visible al rechazar una transición.

El seguimiento debe indicar qué ocurrió, quién debe actuar y qué condición falta. En no críticas, análisis y correctivas se muestran «No aplica». El avance de acciones no se presenta como evaluación de eficacia. Las tablas anchas admiten scroll horizontal y el layout se apila en pantallas menores.

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
| Tipo «No Conformidad» frente a «No Conforme» | FOR validación Formato!C5:G5 frente a TEC §§26, 74 | Conservar código NOC y etiqueta explícita de plataforma «No Conforme», reconociendo alias documental «No Conformidad». Diferencia registrada y reversible; no modificar la fuente oficial. |
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

## Modelo, permisos y decisiones

Hallazgo distingue reportante, responsable y validador, con criterio de categoría, requisito de referencia y prioridad separada. CicloTratamiento conserva reaperturas; análisis, acciones, PBI y evaluaciones apuntan al ciclo. Seguimiento y reprogramación son registros 1:N. Evidencia mantiene contexto compatible; comunicación formal se separa de notificación interna. Las decisiones y tradeoffs están en DECISIONS.md; reglas temporales en ASSUMPTIONS.md; matriz completa de permisos/transiciones en WORKFLOW.md.

Se puede continuar sin consulta bloqueante con Django modular, PostgreSQL, Custom User, permisos combinables, templates derivados, historial, transacciones, secuencias configurables y matriz demo identificada. No hay evidencia de datos productivos existentes que obligue a migrar automáticamente información de la plantilla. No se integran sistemas externos ni se publican sitios durante esta fase.

Las decisiones de adopción productiva sí requieren fuentes y definición de negocio: matriz oficial, comunicación vigente, NA, reasignaciones, cancelación, métricas, retención y alcance de validadores. No se ocultan detrás de valores demo.

## Plan de implementación y aceptación

1. Crear estructura, configuración segura, PostgreSQL aislado, Custom User y grupos/permisos.
2. Crear modelo normalizado, restricciones, migraciones y semillas separadas.
3. Extraer diseño a templates/CSS/SVG; login, dashboards por rol y navegación con alcance.
4. Implementar identificación, borrador, cálculo Python, SAC, validación y devolución.
5. Implementar corrección, comunicación, 6M/controles, PBI manual, plan, seguimientos y reprogramaciones.
6. Implementar evaluación, cierre y nuevos ciclos de reapertura con evidencias y trazabilidad.
7. Implementar búsquedas, administración funcional, notificaciones internas y reportes definidos.
8. Ejecutar pruebas reales en PostgreSQL, permisos negativos, escenarios por ruta y revisión visual. Documentar resultados sin convertir una prueba prevista en una prueba superada.

REQUIREMENTS_TRACEABILITY.md vincula cada regla con responsable técnico, ruta de implementación prevista y prueba necesaria. Los originales DOCX/XLSX permanecen intactos.
