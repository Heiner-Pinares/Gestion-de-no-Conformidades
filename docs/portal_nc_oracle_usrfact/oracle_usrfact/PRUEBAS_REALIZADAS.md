# Evidencia de revisión del paquete Oracle

Fecha de revisión: 09/10/2026.

## Pruebas completadas

- Validador estático `scripts/validar_oracle_usrfact.py`: aprobado.
- Inventario: 24 tablas y 229 columnas, comparadas con el esquema PostgreSQL vigente.
- Integridad: 44 claves foráneas, 22 identidades, 22 reajustes de identidad, 40 índices explícitos y 11 triggers.
- Datos base: 29 catálogos, 1 configuración de impacto, 2 configuraciones de urgencia, 9 combinaciones de prioridad y 32 preguntas 6M.
- Línea base Django: las 56 filas coinciden exactamente con las 56 migraciones disponibles de las aplicaciones instaladas.
- Permisos: cobertura estática exacta de 24 tablas × 4 privilegios × 3 usuarios = 288 privilegios.
- Parser SQL Oracle independiente: 263 sentencias de tablas, relaciones, índices, datos base, línea base y permisos analizadas sin errores. La cláusula Oracle específica `START WITH LIMIT VALUE` se valida por patrón y contra la documentación oficial de Oracle 19c porque el parser externo no la implementa.
- `python manage.py check`: aprobado, cero observaciones.
- `python manage.py makemigrations --check --dry-run`: aprobado, sin cambios pendientes.
- Suite funcional actual sobre PostgreSQL: 64 pruebas ejecutadas, 64 aprobadas.

## Pruebas incluidas para ejecutar en Oracle

`08_prueba_humo.sql` realiza inserciones transaccionales en el conjunto de 24 tablas, prueba claves, catálogos, sincronización de roles/validadores, JSON, identidad y lectura/escritura de un BLOB. Sus datos se revierten al final.

`09_validacion_final.sql` comprueba cantidades de objetos, restricciones habilitadas y validadas, triggers válidos, datos base, línea de migraciones, las 22 secuencias de identidad por encima de `MAX(id)`, los 288 privilegios y el tipo BLOB del archivo.

## Límite actual de la validación

No hay una instancia Oracle 19c ni credenciales de homologación disponibles en esta máquina. Por eso no se afirma que el paquete fue ejecutado en Oracle. La aceptación final requiere ejecutar `INSTALAR_USRFACT.sql` en una Oracle 19c de homologación y conservar el log que termine en `INSTALACION COMPLETADA Y VALIDADA`.
