# Despliegue del Portal NC en Windows Server y Oracle

## Arquitectura validada

- Django 5.2.17 y Python 3.12.
- PostgreSQL para desarrollo y Oracle 19c o superior para el servidor.
- `python-oracledb` 4.0.2 en modo Thick para admitir el verificador 10G actual de `USRFACSOP`.
- Oracle Instant Client 19c Basic o Basic Light x64 en `C:\oracle\instantclient_19`.
- Waitress 3.0.2 como servidor WSGI en Windows.
- WhiteNoise 6.12.0 para servir los archivos estáticos recolectados desde el mismo proceso.
- Esquema propietario fijo: `USRFACT`.
- Cuenta de la aplicación: `USRFACSOP`, con solo `CREATE SESSION` y DML sobre las 24 tablas.

El portal nunca ejecuta DDL en Oracle. El DBA instala o actualiza el esquema con SQL revisado. En cada arranque, `run.py` compara la base con el código y se detiene si falta una tabla, columna, migración, trigger, permiso o catálogo indispensable. Esto evita que una cuenta web cree o cambie objetos sin control.

## 1. Instalación de las tablas por el DBA

Conectado como `USRFACT`, el DBA ejecuta en homologación:

```text
docs\oracle_usrfact\INSTALAR_USRFACT_TODO_EN_UNO.sql
```

Debe conservar el log y comprobar que termine con `INSTALACION COMPLETADA Y VALIDADA`. El script concede a la cuenta técnica `USRFACSOP` `SELECT`, `INSERT`, `UPDATE` y `DELETE`. No le concede permisos para crear tablas, columnas, secuencias, restricciones ni triggers.

Como las tablas ya fueron creadas en `USRFACT`, el DBA no debe repetir el
instalador. Primero debe reparar los triggers que fallaron durante la ejecución
anterior. Una cuenta DBA ejecuta:

```sql
GRANT CREATE TRIGGER TO USRFACT;
```

Después, conectado como `USRFACT`, se ejecutan estos dos archivos:

```text
docs\oracle_usrfact\11_reparar_triggers_existentes.sql
docs\oracle_usrfact\10_otorgar_permisos_usrfacsop.sql
```

Ambos se pueden repetir sin duplicar datos. El primero crea o reemplaza los 11
triggers corregidos y comprueba que estén válidos y habilitados. El segundo
concede los cuatro permisos DML a `USRFACSOP` y exige un total de 96. Al final,
el DBA puede retirar el privilegio temporal con:

```sql
REVOKE CREATE TRIGGER FROM USRFACT;
```

## 2. Clonar e instalar en Windows Server

Requisitos: Git, Python 3.12 x64 y acceso de red al servicio Oracle.

```powershell
cd C:\Aplicaciones
git clone <URL-DEL-REPOSITORIO> portal_nc
cd portal_nc
powershell -ExecutionPolicy Bypass -File scripts\instalar_windows_oracle.ps1
```

El instalador es idempotente: reutiliza `.venv`, instala las versiones fijadas en `requirements-oracle.txt`, crea `secrets` y solo copia el ejemplo a `.env` cuando ese archivo no existe.

## 3. Configuración sin secretos en Git

Edite `.env` y complete valores no secretos:

```env
DEBUG=False
ALLOWED_HOSTS=172.19.194.219,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=http://172.19.194.219:8000
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_HSTS_PRELOAD=False
TRUST_X_FORWARDED_PROTO=False

DB_ENGINE=oracle
DB_DSN="(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=scan-dwo.tim.com.pe)(PORT=1521))(CONNECT_DATA=(SERVER=DEDICATED)(SERVICE_NAME=DWO)))"
DB_SCHEMA=USRFACT
DB_USER=USRFACSOP
DB_PASSWORD_FILE=secrets/oracle_password.txt
DB_REQUIRE_DML_ONLY=True
DB_ALLOWED_USERS=USRFACSOP
ORACLE_THICK_MODE=True
ORACLE_CLIENT_LIB_DIR=C:/oracle/instantclient_19

SECRET_KEY_FILE=secrets/django_secret_key.txt
PORTAL_BIND_HOST=0.0.0.0
PORTAL_PORT=8000
PORTAL_THREADS=8
```

`DB_DSN` usa `host:puerto/SERVICE_NAME`. Si el DBA entrega un descriptor TNS completo, colóquelo completo en `DB_DSN`. No use un SID como si fuera `SERVICE_NAME`.

La configuración entregada publica inicialmente por HTTP en `172.19.194.219:8000`. Al habilitar HTTPS en IIS o en el proxy aprobado, cambie `CSRF_TRUSTED_ORIGINS` al origen `https://`, y establezca `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` y `CSRF_COOKIE_SECURE` en `True`. Active `TRUST_X_FORWARDED_PROTO=True` únicamente cuando el proxy elimine cualquier encabezado entrante y establezca por sí mismo `X-Forwarded-Proto`. Active `SECURE_HSTS_PRELOAD=True` solo después de aprobar la inclusión permanente del dominio y sus subdominios en la lista preload de los navegadores.

Cree los secretos sin mostrarlos en pantalla:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\configurar_secretos_windows.ps1 -ServiceAccount DOMINIO\CuentaServicio
```

El script solicita la contraseña Oracle de forma oculta, genera una `SECRET_KEY` independiente y restringe los archivos a la cuenta de servicio indicada. `.env`, `secrets`, logs, medios y estáticos recolectados están excluidos de Git.

## 4. Habilitar Oracle Thick para la cuenta existente

La cuenta `USRFACSOP` usa un verificador de contraseña 10G que no funciona en
modo Thin. Sin intervención del DBA, instale Oracle Instant Client 19c Basic o
Basic Light **x64**, extraiga su contenido y deje `oci.dll` directamente en:

```text
C:\oracle\instantclient_19\oci.dll
```

Instale también Microsoft Visual C++ Redistributable x64 requerido por Oracle
Instant Client. Después ejecute:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\habilitar_oracle_thick_windows.ps1"
```

El script comprueba Python x64, carga realmente `oci.dll` y actualiza solamente
`ORACLE_THICK_MODE` y `ORACLE_CLIENT_LIB_DIR` en `.env`. No muestra ni modifica
la contraseña.

Antes de cada entrega puede comprobar los archivos versionados con:

```powershell
.\.venv\Scripts\python.exe scripts\verificar_secretos_git.py
```

## 5. Comprobar sin iniciar

```powershell
.\.venv\Scripts\python.exe run.py check
```

El comando muestra solamente el servicio, la versión Oracle, el modo Thick, el usuario y el esquema conectados. Comprueba 24 tablas, 229 columnas, 96 permisos DML, 11 triggers válidos y habilitados, el BLOB de evidencias, catálogos mínimos y que las 56 migraciones registradas coincidan exactamente con el checkout. También ejecuta `django check --deploy`. Nunca imprime la contraseña ni el DSN.

## 6. Crear el primer superusuario

```powershell
.\.venv\Scripts\python.exe run.py createsuperuser
```

Este comando solo inserta datos por el ORM luego de validar el esquema. La contraseña se solicita interactivamente.

## 7. Iniciar el portal

Comando único:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\iniciar_windows_oracle.ps1
```

Equivale a:

```powershell
.\.venv\Scripts\python.exe run.py start
```

Primero valida Oracle y Django, luego ejecuta `collectstatic` y finalmente inicia Waitress. Si la configuración, permisos o esquema no coinciden, el proceso termina antes de abrir el puerto. Para producción, ejecute este comando con una cuenta de servicio y publique HTTPS mediante el proxy inverso aprobado (por ejemplo IIS ARR).

## Actualizar desde Git

Detenga el servicio web, respalde `.env` y `secrets`, y ejecute:

```powershell
git fetch --all --prune
git pull --ff-only
powershell -ExecutionPolicy Bypass -File scripts\instalar_windows_oracle.ps1
.\.venv\Scripts\python.exe run.py check
```

Solo reinicie el portal si `run.py check` termina correctamente. Si el nuevo código requiere cambios de modelo, primero debe existir un SQL Oracle revisado y ejecutado por el DBA. `manage.py` bloquea `migrate`, `makemigrations`, `sqlmigrate`, `squashmigrations`, `test` y `flush` cuando `DB_ENGINE=oracle`.

## Las 24 tablas

| Grupo | Tablas | Uso |
|---|---|---|
| Identidad | `tbl_usuario_nc`, `tbl_usuario_rol_nc` | Cuentas, perfil, contraseñas cifradas y roles. |
| Organización | `tbl_proceso_nc`, `tbl_proceso_validador_nc`, `tbl_subproceso_nc` | Procesos, responsables, validadores y subprocesos. |
| Configuración | `tbl_catalogo_nc`, `tbl_configuracion_impacto_nc`, `tbl_configuracion_urgencia_nc`, `tbl_matriz_prioridad_nc`, `tbl_pregunta_causa_nc` | Catálogos y reglas editables de impacto, urgencia, prioridad y causa raíz. |
| Hallazgo | `tbl_registro_general_nc`, `tbl_ciclo_tratamiento_nc`, `tbl_correlativo_sac_nc`, `tbl_pbi_nc` | Registro principal, ciclos, numeración y referencias PBI. |
| Tratamiento | `tbl_actividad_nc`, `tbl_comunicacion_nc`, `tbl_evaluacion_eficacia_nc` | Acciones, seguimientos, comunicaciones y eficacia. |
| Evidencias | `tbl_evidencia_nc`, `tbl_archivo_evidencia_nc` | Metadatos, hash y contenido BLOB completo de cada archivo. |
| Trazabilidad | `tbl_historial_hallazgo_nc`, `tbl_auditoria_administracion_nc`, `tbl_notificacion_nc` | Historial funcional, auditoría administrativa y avisos internos. |
| Django | `tbl_django_session_nc`, `tbl_django_migrations_nc` | Sesiones autenticadas y línea base de compatibilidad del esquema. |

El inventario exacto de columnas y relaciones está en `docs/oracle_usrfact/manifest_esquema.json`. El instalador contiene 44 claves foráneas, identidades, índices, restricciones, triggers y datos maestros.

## Validación final de producción

La preparación local no sustituye una prueba contra Oracle real. Antes del pase deben completarse en homologación:

1. Los 11 triggers reparados y los 96 permisos de `USRFACSOP` validados en el esquema existente.
2. `run.py check` con la cuenta DML real.
3. Inicio de Waitress y acceso HTTP desde el proxy.
4. Creación, tratamiento, evidencia BLOB, evaluación, cierre y descarga de plantillas de un caso de prueba.
5. Confirmación de HTTPS, respaldo/restauración, monitoreo y rotación de secretos.

### Instalaciones con `UK_CAT_CLASE_VALOR_NC`

El portal admite tanto el índice condicional del instalador oficial como una instalación existente con `UK_CAT_CLASE_VALOR_NC UNIQUE (clase, valor)`. En el segundo caso, `seed_initial_data` completa mediante DML los identificadores técnicos de Tipo, Fuente, Prioridad y Categoría antes de crear los registros faltantes. Esos números no se muestran ni se interpretan como niveles de negocio; los niveles continúan siendo exclusivamente Impacto y Urgencia.

No se requiere que `USRFACT` altere la tabla. Con la cuenta de aplicación `USRFACSOP`, ejecute:

```powershell
.\.venv\Scripts\python.exe manage.py seed_initial_data
.\.venv\Scripts\python.exe run.py check
```

El archivo `docs/oracle_usrfact/12_reparar_indice_catalogo_existente.sql` queda como normalización opcional para el propietario del esquema, pero no es necesario para instalar ni arrancar el portal.
