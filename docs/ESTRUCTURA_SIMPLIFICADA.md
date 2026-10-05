# Estructura optimizada: 6 tablas físicas y 0 vistas

La base `gestion_no_conformidades` usa PostgreSQL y contiene exactamente seis tablas físicas. La migración conserva usuarios, catálogos, hallazgos, actividades, ciclos, evaluaciones, evidencias, historial, notificaciones y auditoría.

| # | Tabla | Contenido |
|---|---|---|
| 1 | `usuario` | Credenciales, perfil corporativo, estado y roles funcionales en JSON. |
| 2 | `configuracion` | Catálogos, procesos, subprocesos, validadores, matriz de prioridad, preguntas 6M, rangos de impacto y rangos de urgencia por jefatura. `registro_tipo` separa cada entidad. |
| 3 | `registro_general` | Fila principal de cada hallazgo, con identificación, impacto, rangos seleccionados como fotografía histórica, prioridad, responsable y estado. |
| 4 | `actividad` | Soluciones y acciones del plan, sus responsables, fechas, avance y estado. |
| 5 | `evento` | Ciclos, análisis, PBI, evaluaciones, comunicaciones, evidencias, historial, notificaciones y auditoría. `registro_tipo` separa cada entidad. |
| 6 | `django_migrations` | Historial técnico de migraciones aplicadas. |

No se crean vistas, vistas materializadas, triggers, funciones ni tipos PostgreSQL personalizados. Los índices, secuencias de identidad y restricciones pertenecen internamente a las tablas y permiten buscar, numerar y proteger datos.

## Registro general de 34 columnas

`registro_general` es la tabla principal de hallazgos. La pantalla `/registro-general/` combina en Python esa tabla con `actividad` y `evento` para presentar una fila por actividad y ciclo. Los filtros, paginación y exportación CSV siguen disponibles sin una vista SQL y sin duplicar información.

Los campos `impacto_clientes_seleccion`, `impacto_tiempo_seleccion` e `impacto_financiero_seleccion` guardan el texto exacto del rango mostrado al usuario cuando realiza la evaluación. Los cambios posteriores en la configuración administrativa se aplican a evaluaciones nuevas y no reescriben los hallazgos anteriores.

`urgencia_seleccion` y `urgencia_area` conservan de la misma forma el rango y la jefatura usados en la evaluación de urgencia. La regla activa se resuelve desde `usuario.area`: Facturación usa Emisión de facturación y Post facturación usa Vencimiento de ciclo.

## Modelos lógicos sobre tablas compartidas

El backend usa modelos tipados. Por ejemplo, `Proceso`, `PreguntaCausa`, `ConfiguracionImpacto` y `ConfiguracionUrgencia` consultan `configuracion` filtrando automáticamente su `registro_tipo`; `CicloTratamiento`, `Evidencia` y `Notificacion` hacen lo mismo sobre `evento`. Las reglas y formularios conservan sus APIs de dominio aunque compartan almacenamiento físico.

Los roles `USUARIO`, `VALIDADOR` y `ADMINISTRADOR` se guardan en `usuario.roles`. Los permisos se resuelven en Python. La asignación de validadores de un proceso se guarda en `configuracion.validadores_ids`. La sesión permanece en una cookie firmada HttpOnly.

## Comprobación en pgAdmin

1. Abre `gestion_no_conformidades → Schemas → public → Tables`: deben aparecer las seis tablas de la lista.
2. Abre `Views`: debe estar vacío.
3. Comprueba las tablas con:

```sql
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

SELECT viewname
FROM pg_views
WHERE schemaname = 'public';
```

La primera consulta devuelve seis filas y la segunda ninguna.

## Migración y respaldo

La migración `apps/hallazgos/migrations/0013_seis_tablas_fisicas.py` copia los datos al esquema tipado, actualiza las relaciones y retira los objetos de compatibilidad. Las migraciones 0014 y 0015 completan la compatibilidad de pruebas y eliminan los tipos auxiliares heredados. La migración 0018 agrega las fotografías históricas del impacto y la migración 0020 agrega las de urgencia dentro de `registro_general`.

Respaldo anterior a la reducción: `.runtime/backups/antes-seis-tablas-20260928-213335/antes.dump`.
