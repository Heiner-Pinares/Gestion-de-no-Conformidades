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

__all__ = [
    "actividades_catalogadas",
    "actividades_para",
    "actividades_queryset",
    "catalogo_identificacion",
    "detalle_actividad",
    "guardar_actividad",
    "reparar_textos_corruptos",
    "sincronizar_catalogo_identificacion",
    "subproceso_id_actividad",
]
