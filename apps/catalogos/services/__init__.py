"""Servicios de mantenimiento de los catálogos funcionales."""

from .textos import reparar_textos_corruptos
from .identificacion import (
    actividades_catalogadas,
    actividades_para,
    actividades_queryset,
    catalogo_identificacion,
    detalle_actividad,
    guardar_actividad,
    subproceso_id_actividad,
    sincronizar_catalogo_identificacion,
)
from .correos import (
    TIPO_COPIA,
    TIPO_PARA,
    TIPOS_CORREO,
    correos_queryset,
    destinatarios_adicionales,
    guardar_correo,
    tipo_correo,
)

__all__ = [
    "actividades_catalogadas",
    "actividades_para",
    "actividades_queryset",
    "catalogo_identificacion",
    "detalle_actividad",
    "correos_queryset",
    "destinatarios_adicionales",
    "guardar_actividad",
    "guardar_correo",
    "reparar_textos_corruptos",
    "sincronizar_catalogo_identificacion",
    "subproceso_id_actividad",
    "tipo_correo",
    "TIPO_COPIA",
    "TIPO_PARA",
    "TIPOS_CORREO",
]
