"""Catálogo oficial para Proceso, Subproceso y Actividad de identificación."""

import json
from pathlib import Path

from django.db import transaction

from apps.catalogos.models import Proceso, Subproceso


RUTA_CATALOGO = Path(__file__).resolve().parents[1] / "data" / "procesos_subprocesos.json"


def catalogo_identificacion():
    """Lee la jerarquía versionada con el código y conserva su orden."""
    return json.loads(RUTA_CATALOGO.read_text(encoding="utf-8"))["procesos"]


def actividades_para(proceso, subproceso):
    """Devuelve las actividades admitidas para los nombres indicados."""
    proceso_nombre = proceso.nombre if hasattr(proceso, "nombre") else str(proceso or "")
    subproceso_nombre = subproceso.nombre if hasattr(subproceso, "nombre") else str(subproceso or "")
    for item_proceso in catalogo_identificacion():
        if item_proceso["nombre"] != proceso_nombre:
            continue
        for item_subproceso in item_proceso["subprocesos"]:
            if item_subproceso["nombre"] == subproceso_nombre:
                return tuple(item_subproceso["actividades"])
    return ()


def actividades_catalogadas():
    return tuple(
        actividad
        for proceso in catalogo_identificacion()
        for subproceso in proceso["subprocesos"]
        for actividad in subproceso["actividades"]
    )


@transaction.atomic
def sincronizar_catalogo_identificacion():
    """Activa el catálogo oficial e inactiva el anterior sin borrar históricos."""
    estructura = catalogo_identificacion()
    nombres_proceso = {item["nombre"] for item in estructura}

    procesos_creados = procesos_actualizados = 0
    subprocesos_creados = subprocesos_actualizados = 0
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

    procesos_inactivados = Proceso.objects.exclude(nombre__in=nombres_proceso).filter(activo=True).update(activo=False)
    subprocesos_inactivados = Subproceso.objects.exclude(pk__in=subprocesos_oficiales).filter(activo=True).update(activo=False)

    return {
        "procesos_creados": procesos_creados,
        "procesos_activados": procesos_actualizados,
        "procesos_inactivados": procesos_inactivados,
        "subprocesos_creados": subprocesos_creados,
        "subprocesos_activados": subprocesos_actualizados,
        "subprocesos_inactivados": subprocesos_inactivados,
        "actividades": len(actividades_catalogadas()),
    }
