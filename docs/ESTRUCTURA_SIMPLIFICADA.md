# Estructura optimizada: máximo 10 tablas

## Resultado comprobado

La base `gestion_no_conformidades` de PostgreSQL 5432 tiene **exactamente 10 tablas físicas**. Los datos existentes se conservaron y las 32 pruebas funcionales pasan sobre una base creada desde cero.

```sql
SELECT tablename
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

| N.º | Tabla física | Justificación |
|---:|---|---|
| 1 | `accounts_usuario` | Identidad, contraseña con hash y datos del usuario. |
| 2 | `catalogos_catalogo` | Tipos, fuentes, impacto, urgencia, prioridad y categorías en una tabla discriminada por clase. |
| 3 | `catalogos_proceso` | Gerencia, proceso, responsable y estado activo. |
| 4 | `hallazgos_hallazgo` | Registro principal con los datos de identificación solicitados. |
| 5 | `hallazgos_ciclotratamiento` | Análisis 6M, causa raíz, control, evaluación y cierre por ciclo. |
| 6 | `hallazgos_accion` | Acciones inmediatas/correctivas, responsable, FET, estado y avance. |
| 7 | `hallazgos_historialhallazgo` | Trazabilidad, seguimientos y reprogramaciones. |
| 8 | `hallazgos_correlativosac` | Reserva transaccional del número SAC sin duplicados concurrentes. |
| 9 | `django_migrations` | Control de versión del esquema; evita aplicar cambios dos veces. |
| 10 | `sistema_registro_auxiliar` | Almacén JSON único para registros pequeños y variables. |

## Qué pasó con las tablas anteriores

Matriz de prioridad, preguntas 6M, subprocesos, validadores, roles, permisos, auditoría administrativa, PBI, comunicaciones, evaluaciones, evidencias y notificaciones se concentran en `sistema_registro_auxiliar`. La columna `tipo` separa cada conjunto y `datos` conserva sus campos en JSON.

El backend continúa usando nombres como `catalogos_preguntacausa` o `hallazgos_evidencia` mediante **vistas de compatibilidad tipadas**. Un trigger genérico traduce altas, cambios y eliminaciones a la tabla auxiliar. Esto mantiene los formularios y servicios existentes mientras PostgreSQL cuenta una sola tabla física. Las reglas de negocio y permisos siguen en `apps/hallazgos/services/` y `apps/accounts/permissions.py`.

Las vistas no deben importarse como tablas en Vertabelo. Al crear el modelo, selecciona únicamente **Tables** y excluye **Views**. Para ver el modelo de negocio consolidado, incluye también `registro_general`, que expone las 31 columnas aprobadas sin duplicar información.

## Inicio de sesión sin tabla

`django_session` ya no es una tabla. Django usa `django.contrib.sessions.backends.signed_cookies`: el backend firma el contenido, el navegador lo guarda en una cookie HttpOnly y cada petición valida la firma. La aplicación no crea una fila para medir el inicio ni almacena la contraseña en la cookie.

La duración de ocho horas y el cierre al cerrar el navegador permanecen configurados en `config/settings.py`. El inicio de sesión conserva CSRF, hash de contraseña, SameSite y cierre por POST.

## Registro general de 31 columnas

`public.registro_general` es una vista de consulta con las columnas pedidas: gerencia, proceso, subproceso, fuente, tipo, número de hallazgo, Remedy, descripción, referencia, responsables, fechas, impacto, urgencia, prioridad, criticidad, causa raíz, acción, FET, estado, evidencia, avance, eficacia, cierre y comentarios.

En pgAdmin:

1. Actualiza `gestion_no_conformidades → Schemas → public` con **Refresh**.
2. Abre **Tables**: deben aparecer las 10 tablas de este documento.
3. Abre **Views → registro_general** para consultar la matriz de 31 columnas.
4. Ejecuta `SELECT * FROM public.registro_general ORDER BY numero;` si quieres verla en Query Tool.

## Ejecutar manualmente

El portal queda detenido. Para iniciarlo tú mismo:

```sh
cd "/Users/heinerpinares/Documents/Gestion de no Conformidades/Automatizacion/portal_nc"
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Luego abre `http://127.0.0.1:8000/`. Para detenerlo, vuelve a esa Terminal y pulsa `Ctrl+C`. PostgreSQL debe permanecer encendido; no necesitas volver a ejecutar migraciones ni semillas.

## Dónde entender el código

1. `apps/hallazgos/models.py`: expediente, ciclos, acciones, evidencias e historial.
2. `apps/hallazgos/services/`: validaciones y transacciones de cada etapa.
3. `apps/catalogos/models.py`: catálogos, procesos, matriz y preguntas 6M.
4. `apps/accounts/permissions.py`: roles y alcance por proceso.
5. `apps/hallazgos/registro.py`: contrato de las 31 columnas.
6. `docs/registro_general.sql`: consulta consolidada.
7. `apps/hallazgos/migrations/0006_maximo_diez_tablas.py`: compactación y vistas de compatibilidad.
8. `config/settings.py`: conexión PostgreSQL y sesión firmada.

## Comprobaciones y respaldo

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test apps.hallazgos.tests
.venv/bin/python scripts/verificar_migracion_compacta.py
```

Respaldo anterior a esta reducción: `.runtime/backups/maximo-10-tablas-20260922-222739/antes.dump`. El archivo `codigo-antes.tar.gz` contiene el código previo. La migración es deliberadamente irreversible hacia atrás; para recuperar el diseño anterior se restaura el respaldo en otra base y se valida antes de cambiar la conexión.

La matriz inicial conserva su condición DEMO hasta que negocio apruebe sus valores. La reducción física no cambia esa regla ni inventa integraciones externas.
