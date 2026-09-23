> Registro de la implementación inicial. La estructura vigente y su validación se describen en [ESTRUCTURA_SIMPLIFICADA.md](ESTRUCTURA_SIMPLIFICADA.md); esa actualización reemplaza las referencias a tablas que se consolidaron.

# Contrato interno de implementación

Django 5.2 LTS, Python 3.12, PostgreSQL real. Todas las apps `apps.<nombre>`.

## Accounts
Usuario(AbstractUser): area, cargo, corporate_identifier (único nullable).
Permisos funcionales en Usuario.Meta.permissions: registrar_hallazgo, validar_hallazgo, gestionar_tratamiento, evaluar_eficacia, cerrar_hallazgo, ver_todos_hallazgos, administrar_plataforma.
Permisos se consultan `accounts.<codename>`. Roles USUARIO, VALIDADOR, ADMINISTRADOR. Admin no recibe validar/gestionar/evaluar/cerrar automáticamente.
Funciones `apps.accounts.permissions.es_administrador(user)`, `es_validador(user)`, `puede_ver(user,hallazgo)`, `puede_gestionar(user,hallazgo)` (responsable con permiso registrar o validador asignado), `puede_validar(user,hallazgo)` (permiso y Proceso.validadores; nunca autor). Superuser técnico no puede autovalidar.
Context processor `apps.accounts.context_processors.perfil`: `es_admin`, `es_calidad`, `puede_registrar`, `roles_usuario`, `notificaciones_no_leidas`.
Login /cuentas/login/, logout POST /cuentas/logout/. Home `/` name `inicio` pertenece hallazgos.urls sin namespace.

## Catálogos
TipoRegistro(codigo PK str(3),nombre,activo)
FuenteDeteccion(codigo PK str(30),nombre,activo)
Proceso(id,nombre,activo,responsable FK Usuario nullable,validadores M2M Usuario)
Subproceso(id,proceso FK,nombre,activo)
Impacto(valor PK PositiveSmallInt,nombre,activo), Urgencia(valor PK PositiveSmallInt,nombre,activo)
Prioridad(codigo PK str(20),nombre,activo)
MatrizPrioridad(id,impacto FK,urgencia FK,prioridad FK,activo,es_demo), Unique(impacto,urgencia)
EstadoHallazgo(codigo PK str(30),nombre,orden) con los 13 estados aprobados. Estructural, no editar códigos/estado desde formularios.
CategoriaCausa(codigo PK str(2),nombre,orden,activo), PreguntaCausa(codigo PK str(8),categoria FK,texto,orden,activo). Seed extrae 32 textos EXACTOS HTML. Editable por admin con historial snapshot.

## Dominio
Usar UN app hallazgos modular (models/, services/ aceptables). Reexportar entidades desde models.
Hallazgo: codigo único, titulo, tipo_registro FK, fuente_deteccion FK, proceso FK, subproceso FK nullable, descripcion, ticket_remedy, responsable FK, registrado_por FK, fecha_deteccion DateTime, fecha_registro DateTime auto, fecha_solucion Date nullable en borrador, impacto_clientes/tiempo/soles/resultante int nullable, urgencia FK nullable, prioridad FK nullable, prioridad_snapshot str, es_critica choices SI/NO/NA (blank borrador), origen_tecnologico bool, estado FK EstadoHallazgo (estado_id = código), version int, updated_at, updated_by. Código inmutable, tipo inmutable tras creación (devolver error si intentan cambiar; documentar). Draft permite campos incompletos salvo tipo/título/proceso/responsable. No cambios manuales de estado.
CicloTratamiento: hallazgo FK related_name ciclos, numero, motivo, creado_por, fecha_inicio, fecha_fin nullable; unique hallazgo/numero. Hallazgo.ciclo_actual property devuelve último.
AnalisisCausa: ciclo OneToOne related_name analisis, responsable FK, causa_raiz Text, fecha_inicio, fecha_finalizacion nullable. 1 análisis por ciclo, muchos por Hallazgo.
RespuestaCausa: analisis FK related_name respuestas, pregunta FK, codigo_snapshot, texto_snapshot, respuesta SI/NO/NA, comentario, usuario, fecha. unique análisis/pregunta.
ControlProceso: analisis OneToOne related_name control, tipos JSON list PREVENTIVO/DETECTIVO/CORRECTIVO, nombre, descripcion, mitiga_riesgo SI/NO/NA, frecuencia, responsable texto, evidencia texto (referencia). Obligatorio cuando 4.1 SI.
Accion: ciclo FK related_name acciones, codigo único `<SAC>-A01` contador por hallazgo, tipo INMEDIATA/CORRECTIVA, descripcion,responsable,fecha_inicio,fet_inicial,fecha_vigente,fecha_real nullable,estado PENDIENTE/EN_PROCESO/COMPLETADA,porcentaje_avance 0..100,resultado_esperado,comentario,created_at,updated_at. Conceptos diferenciados por tipo; conservar histórica.
ReprogramacionAccion: accion FK related_name reprogramaciones, numero_reprogramacion,fecha_anterior,nueva_fecha,motivo,usuario,fecha_registro; unique acción/número, máximo3 transaccional.
SeguimientoAccion: accion FK related_name seguimientos,estado,porcentaje_avance,comentario,usuario,fecha.
PBI: ciclo FK related_name pbis,numero_pbi,ticket_incidente,sistema,herramienta (Helix manual),responsable_ti FK,estado ABIERTO/CERRADO,fecha_creacion,fecha_cierre nullable,observacion. Sin integración externa.
EvaluacionEficacia: ciclo FK related_name evaluaciones,evaluador,fecha_evaluacion Date,resultado EFICAZ/NO_EFICAZ,comentario,fecha_registro.
CierreHallazgo: hallazgo FK related_name cierres,ciclo FK,responsable_cierre,fecha_cierre,observaciones,resultado.
ComunicacionHallazgo: ciclo FK related_name comunicaciones,registrado_por,destinatarios,medio,descripcion,fecha. Registro manual, NO envío externo.
Evidencia: hallazgo FK related_name evidencias,accion FK nullable,analisis FK nullable,evaluacion FK nullable,cierre FK nullable,archivo FileField con UUID,nombre_original,mime_type,tamanio,subido_por,fecha_carga,descripcion. Al máximo un contexto; mismo caso. Sólo descarga con autorización (sin media públicas).
HistorialHallazgo: hallazgo FK related_name historial,usuario,fecha_hora,accion,estado_anterior,estado_nuevo,comentario,metadata_json. Append-only interfaz.
Notificacion: usuario FK related_name notificaciones,hallazgo FK,tipo,titulo,mensaje,leida,fecha_creacion,fecha_lectura.
CorrelativoSAC: anio,ambito str (tipo o GLOBAL),ultimo_numero unique(anio,ambito); settings.SAC_SEQUENCE_SCOPE = TYPE/YEAR. Cambiar modo requiere control/no reiniciar numeración.

## Servicios API (backend exportar desde apps.hallazgos.services)
Todos keyword args y retornan objeto actualizado. Validan permiso, estado y datos; bloquean fila Hallazgo antes de dependencias. ValidationError para negocio, PermissionDenied para permiso.
HallazgoService.crear(*,usuario,datos,borrador=True)
HallazgoService.actualizar(*,usuario,hallazgo,datos,version=None)
WorkflowService.ejecutar(*,usuario,hallazgo,accion,comentario='',version=None)
Acciones workflow: enviar,devolver,validar,cancelar,iniciar_inmediata,iniciar_analisis,iniciar_pbi,planificar,iniciar_implementacion,enviar_verificacion,reabrir,cerrar. `reabrir` manual cerrado sólo evaluador/cierre con motivo; nueva ciclo. No eficaz crea ciclo automáticamente.
CausaService.guardar(*,usuario,hallazgo,datos,finalizar=False) (datos incluye respuestas [{pregunta:obj,respuesta,comentario}], control dict,causa_raiz)
AccionService.crear(*,usuario,hallazgo,datos)
AccionService.seguir(*,usuario,accion,datos)
AccionService.reprogramar(*,usuario,accion,nueva_fecha,motivo)
EficaciaService.evaluar(*,usuario,hallazgo,datos)
PBIService.guardar(*,usuario,hallazgo,datos)
ComunicacionService.registrar(*,usuario,hallazgo,datos)
EvidenciaService.subir(*,usuario,hallazgo,archivo,descripcion='',accion=None,analisis=None,evaluacion=None,cierre=None)

## Forms API
HallazgoForm(data=None,instance=None,usuario=None) ModelForm solo fields autorizados; `datos` cleaned_data; borrador entrada no completa se valida al enviar. Fecha mínima en form/servicio.
TransicionForm: comentario,version(optional),confirmar(required checkbox). Para todas transiciones, comentario servicio obligatorio en devolución/cancelación/reabrir/cerrar.
AnalisisCausaForm: dinámico campos r_<codigo con punto reemplazado _>, c_<...>, causa_raiz, campos control_*; método datos_servicio() luego is_valid. `__init__(data=None,instance=None)`.
AccionForm: ModelForm campos tipo,descripcion,responsable,fecha_inicio,fet_inicial,resultado_esperado,comentario.
SeguimientoForm: estado,porcentaje_avance,fecha_real,comentario.
ReprogramacionForm: nueva_fecha,motivo.
EvaluacionEficaciaForm: fecha_evaluacion,resultado,comentario.
PBIForm: campos PBI salvo ciclo/fechas creación.
ComunicacionForm: destinatarios,medio,descripcion,fecha.
EvidenciaForm: archivo,descripcion.
BuscarHallazgoForm: codigo,estado,tipo_registro,proceso,fecha_desde,fecha_hasta (opcionales).

## Selectors API
`hallazgos_visibles(usuario)` scoped queryset select_related, `acciones_disponibles(usuario,hallazgo)` lista de (codigo,etiqueta); `timeline_hallazgo(hallazgo)` lista dict etiqueta/estado (Completado/Actual/Pendiente/No aplica), `indicadores(usuario)` dict numéricos; dashboard y reportes filtran alcance.

## Workflow acordado
Se retienen 13 estados. Borrador/devuelto -> pendiente -> validado (o devolución/cancelación por no corresponde). Validador asignado, distinto reportante. Validado -> ACCION_INMEDIATA crea primer ciclo si falta. Registrar acción inmediata, completar y registrar comunicación antes avanzar. Crítica -> EN_ANALISIS requiere 32 respuestas + causa raíz para PLAN_ACCION; crítica tecnológica pasa PBI_EN_GESTION y exige referencia PBI manual antes plan. DOC-CAT-001 ausente: criticidad tecnológica determinada manualmente, registrar limitación.
No crítica: causa y AC No aplica, pasa EN_VERIFICACION al completar inmediata + comunicación. Criticidad NA pendiente: bloquear envío hasta SI/NO (campo se conserva), reversible.
Plan -> EN_IMPLEMENTACION exige >=1 correctiva y análisis completo del ciclo; -> EN_VERIFICACION exige todas acciones ciclo completadas + comunicación + PBI cerrado si requerido. EFICAZ mantiene EN_VERIFICACION habilita cerrar; NO_EFICAZ -> REABIERTO crea ciclo nuevo. Reabierto -> inmediata (permite no crítica) o análisis crítica (exige tratamiento inmediato + comunicación aplicables del nuevo ciclo; no saltar). Cerrado no se edita.
Guards deben ejecutarse Python para URL/POST directo. Administrador no transiciona sin rol adicional.
