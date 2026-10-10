# Requisitos para conectar el portal a Oracle

La instalación SQL deja listo el esquema `USRFACT`. El portal ya admite elegir Oracle mediante variables de entorno, pero el cambio debe probarse primero contra una base Oracle de homologación.

## Controlador y versión

- Oracle Database 19c o superior.
- Django 5.2.17.
- `python-oracledb` 4.0.2 en modo Thin, definido en `requirements-oracle.txt`.
- `waitress` para servir Django en Windows, incluido en `requirements-oracle.txt`.

## Variables de conexión

Se deben recibir del DBA estos datos y escribirlos en `.env`, usando `.env.oracle.example` como guía:

- host y puerto;
- `SERVICE_NAME` o cadena Easy Connect completa;
- usuario DML de la aplicación (`C27826`, `C28111` o `C28134`);
- contraseña en `secrets/oracle_password.txt` mediante `DB_PASSWORD_FILE`, nunca dentro del repositorio ni del `.env`;
- política TLS y tiempo de espera;
- dominio, HTTPS y secretos de la aplicación.

`DB_ENGINE=oracle` activa `django.db.backends.oracle`; `DB_DSN` recibe una cadena Easy Connect como `host:1521/servicio`.

## Propiedad del esquema

Las tablas pertenecen a `USRFACT`.

- El portal rechaza conectarse como `USRFACT` cuando `DB_REQUIRE_DML_ONLY=True`.
- Al abrir cada conexión Oracle, configura `CURRENT_SCHEMA=USRFACT`. Esto resuelve los nombres sin conceder permisos adicionales.
- La conexión se rechaza si la cuenta tiene privilegios de sistema distintos de `CREATE SESSION`.
- `C27826`, `C28111` y `C28134` reciben exactamente `SELECT`, `INSERT`, `UPDATE` y `DELETE` sobre las 24 tablas.

## Migraciones

No debe ejecutarse el historial antiguo de migraciones para crear esta base. `05_baseline_django.sql` registra las 56 migraciones vigentes después de que los scripts hayan creado la estructura final.

Para cambios futuros, el equipo debe entregar al DBA un script Oracle versionado y, después de aprobarlo, registrar la nueva migración. No se debe usar `migrate --fake` sin comparar antes el esquema real.

`manage.py` bloquea `migrate`, `makemigrations`, `sqlmigrate`, `squashmigrations`, `test` y `flush` cuando `DB_ENGINE=oracle`. El control definitivo sigue siendo la ausencia de privilegios DDL en la cuenta de conexión.

## Compatibilidad revisada en el código

Las consultas que antes aplicaban `DISTINCT` sobre modelos con campos `TextField` o `JSONField` fueron cambiadas para deduplicar solo IDs. Oracle no permite `SELECT DISTINCT` sobre `NCLOB`.

Antes del pase faltará ejecutar, en homologación Oracle:

1. `INSTALAR_USRFACT_TODO_EN_UNO.sql` completo.
2. `run.py check` con la cuenta DML.
3. `run.py start` y los 64 casos funcionales contra Oracle.
4. Una carga de copia anonimizada de datos de PostgreSQL.
5. Pruebas de carga y descarga de archivos BLOB, concurrencia de correlativos, sesiones, permisos y cierre de hallazgos.
