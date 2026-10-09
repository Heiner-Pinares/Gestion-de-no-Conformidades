# Despliegue del Portal NC en Windows con Oracle

## Separación obligatoria de cuentas

- `USRFACT` es únicamente el propietario del esquema. Se usa una sola vez para ejecutar `docs/oracle_usrfact/INSTALAR_USRFACT_TODO_EN_UNO.sql`.
- El portal se conecta con **una** cuenta DML: `C27826`, `C28111` o `C28134`.
- El código rechaza el arranque en modo Oracle si `DB_USER=USRFACT`.
- La cuenta del portal solo necesita `CREATE SESSION` y los `SELECT`, `INSERT`, `UPDATE` y `DELETE` que concede el instalador. No se le debe conceder `CREATE TABLE`, `ALTER ANY TABLE`, `DROP ANY TABLE`, `CREATE TRIGGER`, `CREATE PROCEDURE` ni privilegios `ANY`.
- `ALTER SESSION SET CURRENT_SCHEMA=USRFACT` solo resuelve los nombres de las tablas; no modifica objetos ni entrega privilegios adicionales.

## Preparación del servidor

1. Instale una versión de Python compatible con Django 5.2 y cree el entorno:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\pip.exe install -r requirements-oracle.txt
   ```

2. Copie `.env.oracle.example` como `.env` y complete el DSN, contraseña, dominio y orígenes HTTPS. No use `USRFACT` en `DB_USER`.
3. El DBA ejecuta el instalador conectado como `USRFACT` en una Oracle 19c de homologación y conserva el log que termine en `INSTALACION COMPLETADA Y VALIDADA`.
4. Antes del primer arranque ejecute:

   ```powershell
   .\.venv\Scripts\python.exe scripts\verificar_oracle_dml.py
   ```

   Esta verificación solo consulta metadatos y datos. Exige las 24 tablas, 229 columnas, 96 permisos DML para la cuenta conectada, línea base y BLOB de evidencias.
5. Inicie el portal:

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\iniciar_windows_oracle.ps1
   ```

## Comandos prohibidos en el servidor

No ejecute `migrate`, `makemigrations`, `sqlmigrate`, las pruebas de Django ni scripts PostgreSQL en el servidor Oracle. Cualquier cambio futuro de modelo requiere un script Oracle revisado y ejecutado por el DBA; la cuenta del portal carece de permisos DDL.

## Aceptación antes de producción

La estructura y el código pueden revisarse sin Oracle, pero el pase solo se acepta después de ejecutar el instalador y la verificación DML en una Oracle 19c de homologación, probar los flujos funcionales completos y confirmar respaldo/restauración, HTTPS, secretos, servicio Windows y monitoreo.
