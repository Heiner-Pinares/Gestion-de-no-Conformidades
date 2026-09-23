> Registro de la implementación inicial. La estructura vigente y su validación se describen en [ESTRUCTURA_SIMPLIFICADA.md](ESTRUCTURA_SIMPLIFICADA.md); esa actualización reemplaza las referencias a tablas que se consolidaron.

# Resultado de la implementación local

Fases 0–28 agrupadas en una primera versión funcional: análisis, Django/PostgreSQL, usuario personalizado, roles, modelos/migraciones, semilla, templates, registro/SAC/impacto/prioridad, validación, tratamiento, 6M, acciones, reprogramación, seguimiento, eficacia, cierre/reapertura, administración, notificaciones, historial, reportes, pruebas y documentación.

## Archivos y componentes entregados

- Original HTML conservado en references; CSS y SVG extraídos sin sustituir el diseño.
- Configuración config/settings.py; tres migraciones iniciales (accounts, catalogos, hallazgos).
- Modelos y formularios en apps/accounts, apps/catalogos y apps/hallazgos.
- Servicios explícitos en apps/hallazgos/services; consultas con alcance en selectors.py.
- Rutas propias de negocio y administración, templates por etapa, formularios GET/POST sin JavaScript de negocio.
- README, análisis formal, supuestos, decisiones, workflow y trazabilidad.

## Verificación

23 pruebas sobre PostgreSQL real: flujos crítico/no crítico, PBI, 6M, corrección, reapertura, roles, permisos de objeto, archivos privados, CSRF/XSS, semillas, vencimientos, atomicidad, concurrencia de SAC y doble validación. Migraciones aplicadas, check sin errores y makemigrations sin cambios pendientes. Login y formularios verificables por HTTP. Revisión visual del login, panel y registro a 1366 px y adaptación del panel a tablet de 768 px.

## Uso

La base local está iniciada en puerto 55432. El servidor de desarrollo utiliza 8000. Las tres cuentas demo están creadas sin clave utilizable hasta que el usuario ejecute seed_demo_data de forma interactiva; las contraseñas se guardan con hash Django. Consulta los comandos exactos en README.

## Pendientes y límites

No es un despliegue de producción. Faltan confirmaciones de negocio descritas en ASSUMPTIONS.md, especialmente matriz oficial, NA, escalamiento posterior y política de cancelación. SSO/LDAP, Helix/Remedy, correo y otras integraciones no se han implementado por instrucción. No se ha programado ninguna automatización externa. La inspección visual no cubre todos los navegadores ni todas las resoluciones.
