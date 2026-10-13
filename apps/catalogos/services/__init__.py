"""Servicios de mantenimiento de los catálogos funcionales."""

from .textos import reparar_textos_corruptos
from .identificacion import (
    actividades_catalogadas,
    actividades_para,
    catalogo_identificacion,
    sincronizar_catalogo_identificacion,
)

__all__ = [
    "actividades_catalogadas",
    "actividades_para",
    "catalogo_identificacion",
    "reparar_textos_corruptos",
    "sincronizar_catalogo_identificacion",
]
