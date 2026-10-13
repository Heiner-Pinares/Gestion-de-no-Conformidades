"""Catálogo oficial para Proceso, Subproceso y Actividad de identificación."""

import json
from pathlib import Path
from uuid import uuid4

from django.db import transaction

from apps.catalogos.models import Catalogo, Proceso, Subproceso


RUTA_CATALOGO = Path(__file__).resolve().parents[1] / "data" / "procesos_subprocesos.json"
PREFIJO_ACTIVIDAD = "ACT_"


def catalogo_identificacion():
    """Lee la jerarquía versionada con el código y conserva su orden."""
    return json.loads(RUTA_CATALOGO.read_text(encoding="utf-8"))["procesos"]


def actividades_para(proceso, subproceso):
    """Devuelve desde la tabla maestra las actividades activas del subproceso."""
    if not proceso or not subproceso or subproceso.proceso_id != proceso.pk:
        return ()
    return tuple(
        actividades_queryset()
        .filter(codigo__startswith=f"{PREFIJO_ACTIVIDAD}{subproceso.pk}_", activo=True)
        .order_by("orden", "pk")
        .values_list("nombre", flat=True)
    )


def actividades_catalogadas():
    return tuple(actividades_queryset().filter(activo=True).order_by("orden", "pk").values_list("nombre", flat=True))


def actividades_queryset():
    return Catalogo.objects.filter(clase="CATEGORIA", codigo__startswith=PREFIJO_ACTIVIDAD)


def subproceso_id_actividad(actividad):
    try:
        prefijo, subproceso_id, _ = actividad.codigo.split("_", 2)
        return int(subproceso_id) if prefijo == "ACT" else None
    except (AttributeError, TypeError, ValueError):
        return None


def detalle_actividad(actividad):
    subproceso_id = subproceso_id_actividad(actividad)
    subproceso = Subproceso.objects.select_related("proceso").filter(pk=subproceso_id).first()
    return {
        "proceso": subproceso.proceso if subproceso else None,
        "subproceso": subproceso,
        "nombre": actividad.nombre,
        "activo": actividad.activo,
    }


def _codigo_actividad(subproceso, sufijo=None):
    sufijo = sufijo or uuid4().hex[:6].upper()
    return f"{PREFIJO_ACTIVIDAD}{subproceso.pk}_{sufijo}"


def guardar_actividad(*, subproceso, nombre, activo, actividad=None):
    """Crea o edita una actividad dentro de tbl_catalogo_nc mediante DML."""
    if actividad is None:
        codigo = _codigo_actividad(subproceso)
        while Catalogo.objects.filter(clase="CATEGORIA", codigo=codigo).exists():
            codigo = _codigo_actividad(subproceso)
        actividad = Catalogo(clase="CATEGORIA", codigo=codigo)
    else:
        sufijo = actividad.codigo.split("_", 2)[-1]
        actividad.codigo = _codigo_actividad(subproceso, sufijo)
    actividad.nombre = nombre.strip()
    actividad.activo = activo
    actividad.save()
    return actividad


@transaction.atomic
def sincronizar_catalogo_identificacion():
    """Activa el catálogo oficial e inactiva el anterior sin borrar históricos."""
    estructura = catalogo_identificacion()
    nombres_proceso = {item["nombre"] for item in estructura}

    procesos_creados = procesos_actualizados = 0
    subprocesos_creados = subprocesos_actualizados = 0
    actividades_creadas = 0
    subprocesos_oficiales = []
    for item_proceso in estructura:
        legado = Proceso.objects.filter(nombre="Facturación").first() if item_proceso["nombre"] == "Facturacion" else None
        proceso, creado = Proceso.objects.get_or_create(
            nombre=item_proceso["nombre"],
            defaults={
                "activo": True,
                "gerencia": legado.gerencia if legado else "",
                "responsable_id": legado.responsable_id if legado else None,
                "validadores_ids": list(legado.validadores_ids or []) if legado else [],
            },
        )
        procesos_creados += int(creado)
        if not proceso.activo:
            Proceso.objects.filter(pk=proceso.pk).update(activo=True)
            proceso.activo = True
            procesos_actualizados += 1

        for item_subproceso in item_proceso["subprocesos"]:
            subproceso, creado = Subproceso.objects.get_or_create(
                proceso=proceso,
                nombre=item_subproceso["nombre"],
                defaults={"activo": True},
            )
            subprocesos_creados += int(creado)
            if not subproceso.activo:
                Subproceso.objects.filter(pk=subproceso.pk).update(activo=True)
                subprocesos_actualizados += 1
            subprocesos_oficiales.append(subproceso.pk)
            existentes = actividades_queryset().filter(
                codigo__startswith=f"{PREFIJO_ACTIVIDAD}{subproceso.pk}_",
            ).exists()
            if not existentes:
                for orden, nombre in enumerate(item_subproceso["actividades"], 1):
                    Catalogo.objects.create(
                        clase="CATEGORIA",
                        codigo=_codigo_actividad(subproceso, f"{orden:06d}"),
                        nombre=nombre,
                        activo=True,
                        orden=orden,
                    )
                    actividades_creadas += 1

    procesos_inactivados = Proceso.objects.exclude(nombre__in=nombres_proceso).filter(activo=True).update(activo=False)
    subprocesos_inactivados = Subproceso.objects.exclude(pk__in=subprocesos_oficiales).filter(activo=True).update(activo=False)

    return {
        "procesos_creados": procesos_creados,
        "procesos_activados": procesos_actualizados,
        "procesos_inactivados": procesos_inactivados,
        "subprocesos_creados": subprocesos_creados,
        "subprocesos_activados": subprocesos_actualizados,
        "subprocesos_inactivados": subprocesos_inactivados,
        "actividades_creadas": actividades_creadas,
        "actividades": len(actividades_catalogadas()),
    }
