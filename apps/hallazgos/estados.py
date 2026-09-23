"""Estados estructurales del workflow; las transiciones se validan en Python."""
ESTADOS = [
    ("BORRADOR", "Borrador"), ("PENDIENTE_VALIDACION", "Pendiente de validación"),
    ("DEVUELTO", "Devuelto"), ("VALIDADO", "Validado"),
    ("ACCION_INMEDIATA", "Acción inmediata"), ("EN_ANALISIS", "En análisis"),
    ("PBI_EN_GESTION", "PBI en gestión"), ("PLAN_ACCION", "Plan de acción"),
    ("EN_IMPLEMENTACION", "En implementación"), ("EN_VERIFICACION", "En verificación"),
    ("CERRADO", "Cerrado"), ("REABIERTO", "Reabierto"), ("CANCELADO", "Cancelado"),
]
