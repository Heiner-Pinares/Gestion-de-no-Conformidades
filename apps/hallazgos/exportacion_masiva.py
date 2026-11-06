"""Exportación XLSX de todos los hallazgos desde la administración."""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone

from .models import Accion, CicloTratamiento, Hallazgo


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_TAG = f"{{{NS}}}"
HOJA = "xl/worksheets/sheet1.xml"
PLANTILLA = "plantilla_carga_masiva_hallazgos.xlsx"
ESTILOS_COLUMNAS = [
    "15", "14", "14", "15", "15", "15", "15", "15", "15", "15",
    "17", "17", "17", "15", "12", "12", "15", "15", "15", "15",
    "16", "15", "16", "15", "17", "17", "15", "18", "17", "14",
]
COLUMNAS_NUMERICAS = {15, 16, 28}


def _columna_excel(indice):
    resultado = ""
    while indice:
        indice, resto = divmod(indice - 1, 26)
        resultado = chr(65 + resto) + resultado
    return resultado


def _texto_seguro(valor):
    if valor is None:
        return ""
    texto = str(valor)
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", texto)


def _fecha(valor, *, hora=False):
    if not valor:
        return ""
    if hasattr(valor, "tzinfo") and valor.tzinfo is not None:
        valor = timezone.localtime(valor)
    return valor.strftime("%Y-%m-%d %H:%M" if hora else "%Y-%m-%d")


def _usuario(usuario):
    return usuario.username if usuario else ""


def _fila(hallazgo, ciclo=None, accion=None):
    impacto = hallazgo.impacto_resultante
    if impacto is None:
        valores = [
            valor for valor in (
                hallazgo.impacto_clientes,
                hallazgo.impacto_tiempo,
                hallazgo.impacto_soles,
            ) if valor is not None
        ]
        impacto = max(valores) if valores else ""
    causa_categoria = ciclo.causa_categoria_display if ciclo else ""
    return [
        hallazgo.codigo,
        hallazgo.titulo,
        hallazgo.descripcion,
        hallazgo.tipo_registro.codigo,
        hallazgo.fuente_deteccion.codigo if hallazgo.fuente_deteccion else "",
        hallazgo.proceso.nombre,
        hallazgo.subproceso.nombre if hallazgo.subproceso else "",
        hallazgo.actividad,
        _usuario(hallazgo.responsable),
        _usuario(hallazgo.registrado_por),
        _fecha(hallazgo.fecha_registro, hora=True),
        _fecha(hallazgo.fecha_deteccion, hora=True),
        _fecha(hallazgo.fecha_solucion),
        hallazgo.estado,
        impacto,
        hallazgo.urgencia.valor if hallazgo.urgencia else "",
        hallazgo.es_critica,
        "SI" if hallazgo.origen_tecnologico else "NO",
        hallazgo.ticket_remedy,
        causa_categoria,
        ciclo.causa_raiz if ciclo else "",
        accion.tipo if accion else "",
        accion.descripcion if accion else "",
        _usuario(accion.responsable) if accion else "",
        _fecha(accion.fecha_inicio) if accion else "",
        _fecha(accion.fet_inicial) if accion else "",
        accion.estado if accion else "",
        accion.porcentaje_avance if accion else "",
        _fecha(accion.fecha_real) if accion else "",
        accion.comentario if accion else "",
    ]


def _filas_exportacion():
    acciones = Accion.objects.select_related("responsable").order_by("pk")
    ciclos = CicloTratamiento.objects.select_related(
        "analisis_responsable", "responsable_cierre",
    ).prefetch_related(Prefetch("acciones", queryset=acciones)).order_by("numero")
    hallazgos = Hallazgo.objects.select_related(
        "tipo_registro", "fuente_deteccion", "proceso", "subproceso",
        "responsable", "registrado_por", "urgencia",
    ).prefetch_related(Prefetch("ciclos", queryset=ciclos)).order_by("codigo")

    for hallazgo in hallazgos:
        ciclos_hallazgo = list(hallazgo.ciclos.all())
        if not ciclos_hallazgo:
            yield _fila(hallazgo)
            continue
        for ciclo in ciclos_hallazgo:
            acciones_ciclo = list(ciclo.acciones.all())
            if acciones_ciclo:
                for accion in acciones_ciclo:
                    yield _fila(hallazgo, ciclo, accion)
            else:
                yield _fila(hallazgo, ciclo)


def _escribir_valor(celda, valor, *, numerico=False):
    for hijo in list(celda):
        celda.remove(hijo)
    if valor in (None, ""):
        celda.attrib.pop("t", None)
        return
    if numerico:
        celda.set("t", "n")
        ElementTree.SubElement(celda, f"{NS_TAG}v").text = str(valor)
        return
    celda.set("t", "inlineStr")
    contenido = ElementTree.SubElement(celda, f"{NS_TAG}is")
    texto = ElementTree.SubElement(contenido, f"{NS_TAG}t")
    texto.text = _texto_seguro(valor)


def _rellenar_hoja(contenido, filas):
    raiz = ElementTree.fromstring(contenido)
    datos = raiz.find(f"{NS_TAG}sheetData")
    filas_xml = datos.findall(f"{NS_TAG}row")
    plantillas = filas_xml[1:]

    for numero, valores in enumerate(filas, start=2):
        indice = numero - 2
        if indice < len(plantillas):
            fila = plantillas[indice]
        else:
            fila = ElementTree.SubElement(
                datos,
                f"{NS_TAG}row",
                {"r": str(numero), "ht": "24", "customHeight": "1"},
            )
            for columna, estilo in enumerate(ESTILOS_COLUMNAS, start=1):
                ElementTree.SubElement(
                    fila,
                    f"{NS_TAG}c",
                    {"r": f"{_columna_excel(columna)}{numero}", "s": estilo},
                )
        fila.set("r", str(numero))
        celdas = fila.findall(f"{NS_TAG}c")
        for columna, valor in enumerate(valores, start=1):
            celda = celdas[columna - 1]
            celda.set("r", f"{_columna_excel(columna)}{numero}")
            _escribir_valor(celda, valor, numerico=columna in COLUMNAS_NUMERICAS)

    return ElementTree.tostring(raiz, encoding="utf-8", xml_declaration=True)


def generar_exportacion_masiva():
    """Devuelve un XLSX compatible con la plantilla plana oficial."""
    ruta = Path(settings.BASE_DIR) / "resources" / "plantillas" / PLANTILLA
    filas = list(_filas_exportacion())
    salida = io.BytesIO()
    with zipfile.ZipFile(ruta, "r") as origen, zipfile.ZipFile(
        salida, "w", compression=zipfile.ZIP_DEFLATED,
    ) as destino:
        hoja = _rellenar_hoja(origen.read(HOJA), filas)
        for informacion in origen.infolist():
            destino.writestr(
                informacion,
                hoja if informacion.filename == HOJA else origen.read(informacion.filename),
            )
    return salida.getvalue(), len(filas)
