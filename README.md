# Portal Claro — Gestión de No Conformidades

Primera versión funcional local con Django 5.2 LTS, Python 3.12 y PostgreSQL. Conserva el CSS y los SVG del prototipo v8. La autenticación, autorización, persistencia, workflow y cálculos se ejecutan en Python. No utiliza JavaScript propio ni localStorage para negocio.

## Estructura actual: 10 tablas y Registro general

Se simplificó de 39 a **10 tablas físicas**, conservando funcionalidades y datos. Nueve tablas guardan el núcleo transaccional y `sistema_registro_auxiliar` concentra los registros pequeños en JSON. Las entidades anteriores se exponen como vistas de compatibilidad para el ORM; no son tablas adicionales. La sesión de acceso se firma en una cookie HttpOnly y ya no se persiste en `django_session`.

El menú **Registro general** abre `/registro-general/` con las 31 columnas solicitadas, filtros y exportación CSV. La consulta también está en pgAdmin: `public → Views → registro_general`. Se actualiza al consultar; no duplica datos. Gerencia se completa en Catálogos → Procesos.

Consulta [Estructura simplificada](docs/ESTRUCTURA_SIMPLIFICADA.md) para el mapa actual, la justificación y la forma de verlo en pgAdmin o Vertabelo. Pasaron 32 pruebas sobre PostgreSQL.

## Abrir la instalación preparada en este equipo

La base `gestion_no_conformidades` está en el PostgreSQL existente de `localhost:5432`, junto a `compromisos_db`. La conexión del portal usa su propio rol `portal_nc`, configurado en `.env`.

En Terminal:

```sh
cd "/Users/heinerpinares/Documents/Gestion de no Conformidades/Automatizacion/portal_nc"
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Abre http://127.0.0.1:8000/ . Mantén la Terminal abierta; Ctrl+C detiene la web. PostgreSQL debe estar encendido. No ejecutes `scripts/local_postgres.py start` para esta instalación: era la instancia anterior del puerto 55432.

Usuarios existentes: `usuario.demo`, `validador.demo` y `admin.demo`, con las contraseñas que configuraste. No necesitas ejecutar `seed_demo_data` al iniciar: ese comando vuelve a asignar las contraseñas demo. Para cambiar una sola: `.venv/bin/python manage.py changepassword usuario.demo`.

En pgAdmin, actualiza Databases del servidor PostgreSQL 18 y abre `gestion_no_conformidades → Schemas → public → Tables`. Para consultar una tabla, usa View/Edit Data → All Rows.

La migración original al puerto 5432 conservó los datos y la compactación posterior redujo el esquema a 10 tablas. Se guardó un respaldo inmediatamente anterior en `.runtime/backups/maximo-10-tablas-20260922-222739/`. La copia anterior de `.runtime/postgres` se conserva; los cambios nuevos del portal se guardan en 5432.

## Instalación en otro equipo

Requisitos: Python 3.12, PostgreSQL 14 o superior, pip y capacidad de crear una base. pgAdmin 4 es opcional para administración; la aplicación no depende de él.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configura en `.env`: SECRET_KEY aleatoria, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DEBUG y ALLOWED_HOSTS. `.env` está excluido de Git. No copies claves productivas al repositorio. Genera SECRET_KEY con `python -c "import secrets; print(secrets.token_urlsafe(60))"` y colócala localmente en `.env`.

Crea una base vacía y un usuario propio desde pgAdmin o mediante `createuser --pwprompt portal_nc` y `createdb --owner=portal_nc gestion_no_conformidades` con una cuenta PostgreSQL autorizada. Si usas el script aislado, ejecútalo antes de copiar `.env.example`: crea automáticamente `.env` con valores privados y configura su propia instancia. `PG_BIN` permite indicar la carpeta bin de PostgreSQL; `LOCAL_PG_PORT` permite otro puerto local.

```sh
python manage.py migrate
python manage.py seed_initial_data
python manage.py check
python manage.py runserver
```

Las migraciones están incluidas. No se recrean tablas al arrancar. `makemigrations` se usa únicamente al cambiar modelos. No hay una alternativa SQLite que oculte diferencias de concurrencia.

Para desarrollo, `DEBUG=True` y `ENABLE_DEMO_DATA=True` permiten `python manage.py seed_demo_data`. `--noinput` crea cuentas nuevas con contraseña inutilizable salvo que se suministre DEMO_PASSWORD como variable de entorno del proceso. No persistas esa contraseña en archivos. Los casos demo se distinguen por proceso y descripción. La semilla de maestros no crea cuentas ni casos, y ninguna semilla sobrescribe la matriz que ya hayas configurado.

## Roles y acceso

| Perfil | Función | Alcance |
|---|---|---|
| Usuario | Crear, corregir, enviar y participar | Casos reportados, asignados o donde tenga una acción; edición según etapa y responsabilidad |
| Calidad | Acompañar el tratamiento, evaluar eficacia y cerrar | Solo procesos asignados; no aprueba la identificación inicial |
| Administrador | Usuarios, roles, catálogos, procesos, reportes y auditoría | Configura la plataforma; no valida hallazgos |

Un usuario puede tener varios grupos. El menú combina sus permisos. El administrador asigna validadores desde Catálogos → Procesos. El superusuario técnico se crea con `createsuperuser`; no debe utilizarse como perfil cotidiano de negocio. El admin técnico complementario está en `/admin-tecnico/` y presenta el dominio de tratamiento como consulta.

## Flujo disponible

Borrador → Continuar → Análisis de causa raíz. No existe una aprobación administrativa intermedia: toda NC abre directamente el checklist 6M del paso 2.

Toda NC completa primero el análisis 6M. Después, una NC no crítica registra su acción inmediata y comunicación; una NC crítica habilita además las acciones correctivas. Si además es tecnológica, exige referencia manual PBI. La implementación requiere completar las acciones antes de verificar. Eficaz habilita cierre explícito; No eficaz crea otro ciclo conservando análisis, acciones y evaluación anteriores. La reapertura manual de un cerrado también deja motivo y trazabilidad.

Se conservan los trece estados aprobados. Las transiciones se controlan en `apps/hallazgos/services/workflow.py`, con transacciones y bloqueos por caso. La edición de identificación usa versión para detectar cambios concurrentes. Las acciones tienen código SAC-A01, responsables propios, fechas iniciales inmutables, seguimientos y hasta tres reprogramaciones históricas.

## Datos, archivos y seguridad

- Correlativo por tipo/año de inicio, configurable con SAC_SEQUENCE_SCOPE=TYPE o YEAR. Cambiar el modo con códigos existentes requiere migración controlada; se bloquea el cambio silencioso.
- Impacto = máximo de Clientes/Tiempo/Soles. Prioridad consultada en matriz configurable; una combinación ausente detiene el cálculo con mensaje y log.
- Prioridad operativa y NC crítica son conceptos separados. La matriz inicial es DEMO; no están definidos los umbrales oficiales de clientes, tiempo o soles.
- Custom User desde la primera migración. Contraseñas con hash Django; CSRF, escape de templates, sesiones HTTPOnly y cierre por POST.
- Evidencias PDF/PNG/JPEG hasta 10 MB. Extensión y contenido comprobados, nombre físico UUID, descargas autorizadas y forzadas como adjunto. MEDIA_ROOT no se publica como carpeta web. El reconocimiento de PDF por estructura básica no sustituye un antivirus empresarial.
- Los catálogos se desactivan y las relaciones históricas usan PROTECT. No hay borrado de hallazgos, acciones, evaluaciones ni historial desde la interfaz.
- La auditoría funcional se diferencia de los logs técnicos. Los cambios administrativos conservan valores anteriores/nuevos. CSV protege celdas susceptibles de interpretarse como fórmulas.

## Notificaciones e indicadores

Los cambios del proceso generan avisos internos. No se envían correos ni mensajes externos. Para vencimientos ejecuta explícitamente:

```sh
python manage.py notificar_vencimientos --dias 3
```

Es idempotente por día y acción. No se ha instalado una tarea programada. La ventana de tres días es un parámetro del comando, no una política oficial de Claro.

Un caso vencido tiene fecha de solución anterior a hoy y no está cerrado/cancelado. La eficacia reportada es evaluaciones eficaces / total de evaluaciones, considerando todos los ciclos. Son definiciones documentadas para revisión del negocio; el avance de una acción y su eficacia son distintos.

## Estructura y modelos

- `config/`: configuración y URLs; WSGI/ASGI.
- `apps/accounts/`: Usuario, permisos funcionales, login y grupos.
- `apps/catalogos/`: tipos, fuentes, procesos, subprocesos, impacto, urgencia, prioridad, matriz, estados, categorías/preguntas y auditoría administrativa.
- `apps/hallazgos/`: Hallazgo, correlativo, ciclos, análisis, respuestas, controles, acciones, reprogramaciones, seguimientos, PBI, comunicación, evaluación, cierre, evidencias, historial y notificaciones.
- `services/`: casos de uso con validación/permiso/transacción; `selectors.py`: consultas de alcance; `forms.py`: entrada; `views.py`: adaptación HTTP.
- `templates/`, `static/`: presentación derivada del HTML. SVG originales en includes y CSS original en portal-v8.css.
- `references/`: HTML original intacto.
- `docs/`: auditoría del proceso, supuestos, arquitectura, workflow, trazabilidad y resultado de fases.
- `.runtime/`, `.env`, `media/`, `.venv/`: recursos locales privados, excluidos de Git.

## Pruebas y mantenimiento

```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test apps.hallazgos.tests --noinput
```

La suite utiliza PostgreSQL real y crea/destruye su base de pruebas. La cuenta usada para pruebas necesita CREATEDB; usa una cuenta dedicada fuera de producción. Cubre recorrido crítico/no crítico, avance directo sin aprobación administrativa, controles 6M, PBI, reapertura, cierre, permisos, URLs, CSRF, XSS, evidencias, semillas, límites de reprogramación, atomicidad y concurrencia del SAC.

## Pendientes para adopción productiva

Revisar `docs/ASSUMPTIONS.md`. Faltan DOC-CAT-001 y la definición oficial de comunicación; aprobar matriz, alcance de roles, correlativo, NA, escalamiento de no críticas tras no eficacia y cancelación de acciones. El sistema no cambia automáticamente la criticidad en una reapertura.

SSO/LDAP/Entra ID, Remedy/Helix, correo, antivirus de archivos, límites de intentos de login, backup/restauración y despliegue HTTPS requieren diseño/configuración operacional. No están simulados como integraciones terminadas. El cambio a producción requiere DEBUG=False, dominio autorizado, secretos nuevos, HTTPS, servidor WSGI/ASGI y entrega de estáticos con collectstatic; nunca publicar MEDIA_ROOT directamente. La versión entregada es local y no constituye una certificación productiva del proceso.

Referencia de soporte del framework: https://www.djangoproject.com/download/ y https://docs.djangoproject.com/en/5.2/ .

## Etapas visuales del prototipo aprobado

El indicador compartido muestra las cuatro etapas del HTML v8: Identificación; Análisis de causa raíz; Solución inmediata y acciones correctivas; Evaluación de eficacia y cierre. Los estados y comprobaciones internos se conservan, sin añadir pasos al indicador.
