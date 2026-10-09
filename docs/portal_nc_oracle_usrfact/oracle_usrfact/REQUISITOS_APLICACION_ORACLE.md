# Requisitos para conectar el portal a Oracle

La instalación SQL deja listo el esquema `USRFACT`, pero no cambia la conexión activa del portal. El cambio debe probarse primero contra una base Oracle de homologación.

## Controlador y versión

- Oracle Database 19c o superior.
- Django 5.2.17.
- `python-oracledb` entre 2.3.0 y 4.0.2, definido en `requirements-oracle.txt`.
- Acceso de la cuenta de aplicación a `SYS.DBMS_LOB` y `SYS.DBMS_RANDOM`.

## Variables de conexión pendientes

Se deben recibir del DBA estos datos antes de configurar `settings.py`:

- host y puerto;
- `SERVICE_NAME` o cadena Easy Connect completa;
- usuario técnico de la aplicación;
- contraseña mediante secreto de Windows/servidor, nunca dentro del repositorio;
- política TLS, pool y tiempo de espera;
- tablespace y cuota del esquema propietario.

La configuración usará `ENGINE = "django.db.backends.oracle"`. Cuando `NAME` sea una cadena Easy Connect como `host:1521/servicio`, `HOST` y `PORT` se dejan vacíos.

## Propiedad del esquema

Las tablas pertenecen a `USRFACT`.

- Si el portal se conecta como `USRFACT`, los nombres actuales de los modelos resuelven directamente.
- Si el portal usa otra cuenta técnica, los `GRANT` no bastan para resolver nombres sin esquema. El DBA debe crear sinónimos privados para las 24 tablas o el código debe referirlas como `USRFACT.TBL_*_NC`.
- `C27826`, `C28111` y `C28134` reciben los permisos pedidos, y desde PL/SQL Developer deben consultar como `USRFACT.TBL_REGISTRO_GENERAL_NC`, por ejemplo, salvo que el DBA les cree sinónimos.

## Migraciones

No debe ejecutarse el historial antiguo de migraciones para crear esta base. `05_baseline_django.sql` registra las 56 migraciones vigentes después de que los scripts hayan creado la estructura final.

Para cambios futuros, el equipo debe entregar al DBA un script Oracle versionado y, después de aprobarlo, registrar la nueva migración. No se debe usar `migrate --fake` sin comparar antes el esquema real.

## Compatibilidad revisada en el código

Las consultas que antes aplicaban `DISTINCT` sobre modelos con campos `TextField` o `JSONField` fueron cambiadas para deduplicar solo IDs. Oracle no permite `SELECT DISTINCT` sobre `NCLOB`.

Antes del pase faltará ejecutar, en homologación Oracle:

1. `INSTALAR_USRFACT.sql` completo.
2. La prueba de conexión con la cuenta técnica.
3. `manage.py check` y los 64 casos funcionales contra Oracle.
4. Una carga de copia anonimizada de datos de PostgreSQL.
5. Pruebas de carga y descarga de archivos BLOB, concurrencia de correlativos, sesiones, permisos y cierre de hallazgos.
