"""Reparación conservadora de textos UTF-8 almacenados como Windows-1252."""

import json
from copy import deepcopy
from pathlib import Path

from apps.catalogos.models import Catalogo, PreguntaCausa, Proceso, Subproceso


MARCADORES_MOJIBAKE = ("Ã", "Â", "â€", "ðŸ", "�")


def _puntuacion_mojibake(valor):
    return sum(valor.count(marcador) for marcador in MARCADORES_MOJIBAKE)


def reparar_mojibake(valor):
    """Revierte una o dos decodificaciones equivocadas sin tocar texto válido."""
    if not isinstance(valor, str) or not _puntuacion_mojibake(valor):
        return valor
    mejor = valor
    for _ in range(2):
        candidatos = []
        for codificacion in ("cp1252", "latin1"):
            try:
                candidatos.append(mejor.encode(codificacion).decode("utf-8"))
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        if not candidatos:
            break
        candidato = min(candidatos, key=_puntuacion_mojibake)
        if _puntuacion_mojibake(candidato) >= _puntuacion_mojibake(mejor):
            break
        mejor = candidato
    return mejor


def _catalogo_6m_oficial():
    ruta = Path(__file__).resolve().parents[1] / "data" / "preguntas_6m.json"
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    categorias = {item["codigo"]: item["nombre"] for item in datos}
    preguntas = {
        pregunta["codigo"]: pregunta["texto"]
        for item in datos
        for pregunta in item["preguntas"]
    }
    return categorias, preguntas


def reparar_textos_corruptos():
    """Corrige mojibake en maestros y snapshots históricos del análisis 6M."""
    from apps.hallazgos.models import CicloTratamiento

    categorias_oficiales, preguntas_oficiales = _catalogo_6m_oficial()
    resultado = {"catalogos": 0, "preguntas": 0, "procesos": 0, "subprocesos": 0, "ciclos": 0}

    for catalogo in Catalogo.objects.all().iterator():
        reparado = categorias_oficiales.get(catalogo.codigo) if (
            catalogo.clase == "CATEGORIA"
            and catalogo.codigo in categorias_oficiales
            and _puntuacion_mojibake(catalogo.nombre)
        ) else reparar_mojibake(catalogo.nombre)
        if reparado != catalogo.nombre:
            Catalogo.objects.filter(pk=catalogo.pk).update(nombre=reparado)
            resultado["catalogos"] += 1

    for pregunta in PreguntaCausa.objects.all().iterator():
        reparado = preguntas_oficiales.get(pregunta.codigo) if (
            pregunta.codigo in preguntas_oficiales
            and _puntuacion_mojibake(pregunta.texto)
        ) else reparar_mojibake(pregunta.texto)
        if reparado != pregunta.texto:
            PreguntaCausa.objects.filter(pk=pregunta.pk).update(texto=reparado)
            resultado["preguntas"] += 1

    for modelo, clave in ((Proceso, "procesos"), (Subproceso, "subprocesos")):
        for objeto in modelo.objects.all().iterator():
            reparado = reparar_mojibake(objeto.nombre)
            if reparado != objeto.nombre:
                modelo.objects.filter(pk=objeto.pk).update(nombre=reparado)
                resultado[clave] += 1

    for ciclo in CicloTratamiento.objects.exclude(checklist_snapshot=[]).iterator():
        checklist = deepcopy(ciclo.checklist_snapshot or [])
        respuestas = deepcopy(ciclo.respuestas or [])
        cambio = False
        for item in checklist:
            texto = item.get("texto", "")
            codigo = str(item.get("codigo", ""))
            reparado = preguntas_oficiales.get(codigo) if (
                codigo in preguntas_oficiales and _puntuacion_mojibake(texto)
            ) else reparar_mojibake(texto)
            if reparado != texto:
                item["texto"] = reparado
                cambio = True
        for item in respuestas:
            texto = item.get("texto_snapshot", "")
            codigo = str(item.get("codigo_snapshot", ""))
            reparado = preguntas_oficiales.get(codigo) if (
                not item.get("es_otro")
                and codigo in preguntas_oficiales
                and _puntuacion_mojibake(texto)
            ) else reparar_mojibake(texto)
            if reparado != texto:
                item["texto_snapshot"] = reparado
                cambio = True
        if cambio:
            CicloTratamiento.objects.filter(pk=ciclo.pk).update(
                checklist_snapshot=checklist,
                respuestas=respuestas,
            )
            resultado["ciclos"] += 1
    return resultado
