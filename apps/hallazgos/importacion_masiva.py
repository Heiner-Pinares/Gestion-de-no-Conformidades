"""Importación transaccional de expedientes históricos desde la plantilla XLSX."""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path, PurePosixPath
from uuid import uuid4
from xml.etree import ElementTree

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.catalogos.models import (
    AuditoriaAdministracion, Catalogo, MatrizPrioridad, PreguntaCausa,
    Proceso, Subproceso,
)
from apps.hallazgos.models import (
    Accion, ArchivoEvidencia, CicloTratamiento, ComunicacionHallazgo,
    CorrelativoSAC, EvaluacionEficacia, Evidencia, Hallazgo,
    HistorialHallazgo, PBI,
)
from apps.hallazgos.services.evidencia import MAX_ARCHIVO, validar_archivo
from apps.hallazgos.services.hallazgo import ImpactoService, UrgenciaService


NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
MAX_XLSX = 8 * 1024 * 1024
MAX_ZIP = 80 * 1024 * 1024
MAX_TOTAL_EVIDENCIAS = 60 * 1024 * 1024


REQUERIDAS = {
    "Hallazgos": {"hallazgo_codigo", "titulo", "tipo_codigo", "proceso", "responsable_usuario", "registrado_por_usuario", "fecha_registro", "estado"},
    "Ciclos": {"hallazgo_codigo", "ciclo_numero", "motivo", "creado_por_usuario", "fecha_inicio"},
    "Respuestas_6M": {"hallazgo_codigo", "ciclo_numero", "pregunta_codigo", "respuesta", "usuario", "fecha_hora"},
    "Compromisos": {"hallazgo_codigo", "ciclo_numero", "accion_codigo", "tipo", "descripcion", "responsable_usuario", "fecha_inicio", "fet_inicial", "fecha_vigente", "estado", "porcentaje_avance", "resultado_esperado"},
    "Seguimientos": {"accion_codigo", "seguimiento_numero", "usuario", "fecha_hora", "estado", "porcentaje_avance", "comentario"},
    "Reprogramaciones": {"accion_codigo", "reprogramacion_numero", "usuario", "fecha_hora", "fecha_anterior", "nueva_fecha", "motivo"},
    "Evaluaciones": {"hallazgo_codigo", "ciclo_numero", "evaluacion_numero", "evaluador_usuario", "fecha_evaluacion", "resultado", "comentario", "fecha_registro"},
    "Comunicaciones": {"hallazgo_codigo", "ciclo_numero", "registrado_por_usuario", "destinatarios", "medio", "descripcion", "fecha"},
    "PBI": {"hallazgo_codigo", "ciclo_numero", "numero_pbi", "sistema", "responsable_ti_usuario", "estado", "fecha_creacion"},
    "Evidencias": {"hallazgo_codigo", "contexto", "archivo_ruta", "subido_por_usuario", "fecha_carga"},
}

HOJA_UNICA = "Carga masiva"
COLUMNAS_HOJA_UNICA = {
    "Código hallazgo *": "hallazgo_codigo",
    "Título *": "titulo",
    "Descripción hallazgo": "descripcion",
    "Tipo (código) *": "tipo_codigo",
    "Fuente (código)": "fuente_codigo",
    "Proceso *": "proceso",
    "Subproceso": "subproceso",
    "Actividad": "actividad",
    "Responsable hallazgo *": "responsable_usuario",
    "Registrado por": "registrado_por_usuario",
    "Fecha registro *": "fecha_registro",
    "Fecha detección": "fecha_deteccion",
    "Fecha solución estimada": "fecha_solucion",
    "Estado hallazgo *": "estado",
    "Aplica impacto *": "aplica_impacto",
    "Impacto (1-3)": "impacto",
    "Urgencia (1-3)": "urgencia_valor",
    "Es crítica": "es_critica",
    "Origen tecnológico": "origen_tecnologico",
    "Ticket Remedy": "ticket_remedy",
    "Justificación sin impacto": "justificacion_no_impacto",
    "Causa raíz": "causa_raiz",
    "Responsable análisis": "analisis_responsable_usuario",
    "Inicio análisis": "analisis_inicio",
    "Fin análisis": "analisis_fin",
    "Código compromiso": "accion_codigo",
    "Tipo compromiso": "accion_tipo",
    "Descripción compromiso": "accion_descripcion",
    "Responsable compromiso": "accion_responsable",
    "Inicio compromiso": "accion_fecha_inicio",
    "Fecha límite original": "accion_fet_inicial",
    "Fecha límite compromiso": "accion_fet_inicial",
    "Fecha límite vigente": "accion_fecha_vigente",
    "Estado compromiso": "accion_estado",
    "Avance %": "accion_avance",
    "Fecha real": "accion_fecha_real",
    "Resultado esperado": "accion_resultado",
    "Comentario compromiso": "accion_comentario",
    "Fecha reprogramación": "reprogramacion_fecha",
    "Motivo reprogramación": "reprogramacion_motivo",
    "Resultado eficacia": "eficacia_resultado",
    "Evaluador": "eficacia_evaluador",
    "Evaluador cierre": "eficacia_evaluador",
    "Fecha evaluación": "eficacia_fecha",
    "Comentario evaluación": "eficacia_comentario",
    "Fecha cierre": "fecha_cierre",
    "Responsable cierre": "cierre_responsable",
    "Comentario cierre": "comentario_cierre",
    "Número PBI": "pbi_numero",
    "Sistema PBI": "pbi_sistema",
    "Responsable TI": "pbi_responsable",
    "Estado PBI": "pbi_estado",
    "Fecha creación PBI": "pbi_fecha_creacion",
    "Fecha cierre PBI": "pbi_fecha_cierre",
    "Evidencias (rutas separadas por ;)": "evidencias_rutas",
    "Descripción evidencias": "evidencias_descripcion",
    "Subido por": "evidencias_usuario",
    "Fecha evidencias": "evidencias_fecha",
}


class ErrorCargaMasiva(ValidationError):
    def __init__(self, errores):
        self.errores = list(errores)[:250]
        super().__init__(self.errores)


@dataclass
class PaqueteCarga:
    hojas: dict[str, list[dict]]
    archivos: dict[str, bytes]


def _indice_columna(referencia):
    letras = re.match(r"[A-Z]+", referencia or "")
    resultado = 0
    for letra in letras.group(0) if letras else "":
        resultado = resultado * 26 + ord(letra) - 64
    return resultado - 1


def _texto(elemento):
    return "".join(elemento.itertext()).strip() if elemento is not None else ""


def _leer_xlsx(contenido):
    if len(contenido) > MAX_XLSX:
        raise ErrorCargaMasiva(["El XLSX supera 8 MB."])
    try:
        archivo = zipfile.ZipFile(io.BytesIO(contenido))
    except zipfile.BadZipFile as exc:
        raise ErrorCargaMasiva(["El archivo XLSX está dañado o no corresponde a un libro de Excel."]) from exc
    with archivo:
        if archivo.testzip() is not None:
            raise ErrorCargaMasiva(["El archivo XLSX contiene datos dañados."])
        if sum(info.file_size for info in archivo.infolist()) > 40 * 1024 * 1024:
            raise ErrorCargaMasiva(["El contenido descomprimido del XLSX supera 40 MB."])
        compartidos = []
        if "xl/sharedStrings.xml" in archivo.namelist():
            raiz = ElementTree.fromstring(archivo.read("xl/sharedStrings.xml"))
            compartidos = [_texto(item) for item in raiz.findall(f"{NS}si")]
        libro = ElementTree.fromstring(archivo.read("xl/workbook.xml"))
        relaciones = ElementTree.fromstring(archivo.read("xl/_rels/workbook.xml.rels"))
        destinos = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in relaciones.findall(f"{PKG_REL_NS}Relationship")
        }
        hojas = {}
        for hoja in libro.findall(f"{NS}sheets/{NS}sheet"):
            nombre = hoja.attrib["name"]
            destino = destinos.get(hoja.attrib.get(f"{REL_NS}id"), "")
            if not destino:
                continue
            ruta = destino.lstrip("/")
            if not ruta.startswith("xl/"):
                ruta = "xl/" + ruta
            raiz = ElementTree.fromstring(archivo.read(ruta))
            filas = []
            for numero, fila in enumerate(raiz.findall(f".//{NS}sheetData/{NS}row"), start=1):
                valores = {}
                for celda in fila.findall(f"{NS}c"):
                    indice = _indice_columna(celda.attrib.get("r", ""))
                    tipo = celda.attrib.get("t")
                    if tipo == "inlineStr":
                        valor = _texto(celda.find(f"{NS}is"))
                    else:
                        nodo = celda.find(f"{NS}v")
                        valor = nodo.text if nodo is not None and nodo.text is not None else ""
                        if tipo == "s" and valor != "":
                            valor = compartidos[int(valor)]
                        elif tipo == "b":
                            valor = valor == "1"
                    valores[indice] = valor
                if valores:
                    filas.append((int(fila.attrib.get("r", numero)), [valores.get(i, "") for i in range(max(valores) + 1)]))
            if not filas:
                hojas[nombre] = []
                continue
            encabezados = [str(v).strip() for v in filas[0][1]]
            datos = []
            for numero, valores in filas[1:]:
                registro = {encabezados[i]: valores[i] if i < len(valores) else "" for i in range(len(encabezados)) if encabezados[i]}
                if any(str(v).strip() for v in registro.values()):
                    registro["__fila__"] = numero
                    datos.append(registro)
            hojas[nombre] = datos
        return hojas


def leer_paquete(archivo):
    nombre = Path(archivo.name).name
    contenido = archivo.read(MAX_ZIP + 1)
    if len(contenido) > MAX_ZIP:
        raise ErrorCargaMasiva(["El archivo de carga supera 80 MB."])
    if nombre.lower().endswith(".xlsx"):
        return PaqueteCarga(_leer_xlsx(contenido), {})
    if not nombre.lower().endswith(".zip"):
        raise ErrorCargaMasiva(["Use la plantilla XLSX o un ZIP con la plantilla y sus evidencias."])
    try:
        paquete = zipfile.ZipFile(io.BytesIO(contenido))
    except zipfile.BadZipFile as exc:
        raise ErrorCargaMasiva(["El ZIP está dañado."]) from exc
    with paquete:
        if paquete.testzip() is not None:
            raise ErrorCargaMasiva(["El ZIP contiene un archivo dañado."])
        nombres = [n for n in paquete.namelist() if not n.endswith("/") and not n.startswith("__MACOSX/")]
        for nombre_interno in nombres:
            ruta = PurePosixPath(nombre_interno)
            if ruta.is_absolute() or ".." in ruta.parts:
                raise ErrorCargaMasiva([f"Ruta insegura dentro del ZIP: {nombre_interno}"])
        libros = [n for n in nombres if n.lower().endswith(".xlsx") and not n.startswith("~$")]
        if len(libros) != 1:
            raise ErrorCargaMasiva(["El ZIP debe contener exactamente un archivo XLSX."])
        if paquete.getinfo(libros[0]).file_size > MAX_XLSX:
            raise ErrorCargaMasiva(["El XLSX dentro del ZIP supera 8 MB."])
        archivos = {}
        total = 0
        for interno in nombres:
            if interno == libros[0]:
                continue
            info = paquete.getinfo(interno)
            total += info.file_size
            if info.file_size > MAX_ARCHIVO:
                raise ErrorCargaMasiva([f"La evidencia {interno} supera 10 MB."])
            if total > MAX_TOTAL_EVIDENCIAS:
                raise ErrorCargaMasiva(["Las evidencias del ZIP superan 60 MB en total."])
            archivos[interno.replace("\\", "/")] = paquete.read(interno)
        return PaqueteCarga(_leer_xlsx(paquete.read(libros[0])), archivos)


def _vacio(valor):
    return valor is None or (isinstance(valor, str) and not valor.strip())


def _cadena(valor):
    return "" if valor is None else str(valor).strip()


def _entero(valor, etiqueta, *, minimo=None, maximo=None, requerido=False):
    if _vacio(valor):
        if requerido:
            raise ValueError(f"{etiqueta} es obligatorio")
        return None
    try:
        numero = int(float(valor))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{etiqueta} debe ser un número entero") from exc
    if minimo is not None and numero < minimo or maximo is not None and numero > maximo:
        raise ValueError(f"{etiqueta} debe estar entre {minimo} y {maximo}")
    return numero


def _fecha(valor, etiqueta, *, hora=False, requerido=False):
    if _vacio(valor):
        if requerido:
            raise ValueError(f"{etiqueta} es obligatorio")
        return None
    if isinstance(valor, (int, float)) or re.fullmatch(r"\d+(\.\d+)?", str(valor).strip()):
        resultado = datetime(1899, 12, 30) + timedelta(days=float(valor))
    elif isinstance(valor, datetime):
        resultado = valor
    elif isinstance(valor, date):
        resultado = datetime.combine(valor, time.min)
    else:
        texto = str(valor).strip().replace("T", " ").rstrip("Z")
        resultado = None
        for formato in (None, "%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
            try:
                resultado = datetime.fromisoformat(texto) if formato is None else datetime.strptime(texto, formato)
                break
            except ValueError:
                continue
        if resultado is None:
            raise ValueError(f"{etiqueta} debe usar AAAA-MM-DD o AAAA-MM-DD HH:MM")
    if not hora:
        return resultado.date()
    return timezone.make_aware(resultado) if timezone.is_naive(resultado) else resultado


def _si_no(valor, etiqueta, *, permite_na=False, predeterminado=None):
    if _vacio(valor) and predeterminado is not None:
        return predeterminado
    normal = _cadena(valor).upper()
    equivalencias = {"SÍ": "SI", "YES": "SI", "TRUE": "SI", "1": "SI", "FALSE": "NO", "0": "NO"}
    normal = equivalencias.get(normal, normal)
    permitidos = {"SI", "NO"}
    if permite_na:
        permitidos.add("NA")
    if normal not in permitidos:
        raise ValueError(f"{etiqueta} debe ser {'SI, NO o NA' if permite_na else 'SI o NO'}")
    return normal


def _valor_grupo(filas, campo):
    for fila in filas:
        if not _vacio(fila.get(campo)):
            return fila.get(campo)
    return ""


def convertir_hoja_unica(hojas):
    """Convierte la plantilla plana en las colecciones internas detalladas.

    Una fila representa un compromiso. Las filas con el mismo código se
    agrupan como un solo hallazgo. El formato histórico de varias hojas se
    mantiene disponible para lotes que ya fueron preparados anteriormente.
    """
    if "Hallazgos" in hojas or HOJA_UNICA not in hojas:
        return {nombre: list(filas) for nombre, filas in hojas.items()}
    filas_originales = hojas[HOJA_UNICA]
    if not filas_originales:
        return {"Hallazgos": [], **{nombre: [] for nombre in REQUERIDAS if nombre != "Hallazgos"}}
    presentes = set(filas_originales[0])
    obligatorias = {
        "Código hallazgo *", "Título *", "Tipo (código) *", "Proceso *",
        "Responsable hallazgo *", "Fecha registro *", "Estado hallazgo *",
    }
    faltan = obligatorias - presentes
    if faltan:
        raise ErrorCargaMasiva([f"{HOJA_UNICA}: faltan columnas: {', '.join(sorted(faltan))}."])

    filas = []
    for original in filas_originales:
        fila = {}
        for etiqueta, tecnico in COLUMNAS_HOJA_UNICA.items():
            valor = original.get(etiqueta, "")
            if tecnico not in fila or not _vacio(valor):
                fila[tecnico] = valor
        fila["__fila__"] = original.get("__fila__", "?")
        filas.append(fila)
    grupos = defaultdict(list)
    orden = []
    for fila in filas:
        codigo = _cadena(fila.get("hallazgo_codigo"))
        if not codigo:
            raise ErrorCargaMasiva([f"{HOJA_UNICA}, fila {fila['__fila__']}: Código hallazgo es obligatorio."])
        clave = codigo.casefold()
        if clave not in grupos:
            orden.append(clave)
        grupos[clave].append(fila)

    resultado = {nombre: [] for nombre in REQUERIDAS}
    for clave in orden:
        grupo = grupos[clave]
        principal = grupo[0]
        responsable = principal.get("responsable_usuario")
        registrado = principal.get("registrado_por_usuario") or responsable
        impacto = principal.get("impacto")
        aplica_impacto = principal.get("aplica_impacto")
        if _vacio(aplica_impacto):
            aplica_impacto = (
                "SI"
                if not _vacio(impacto) or not _vacio(principal.get("urgencia_valor"))
                else "NO"
            )
        hallazgo = {
            "__fila__": principal["__fila__"],
            "hallazgo_codigo": principal.get("hallazgo_codigo"),
            "titulo": principal.get("titulo"),
            "descripcion": principal.get("descripcion"),
            "tipo_codigo": principal.get("tipo_codigo"),
            "fuente_codigo": principal.get("fuente_codigo"),
            "proceso": principal.get("proceso"),
            "subproceso": principal.get("subproceso"),
            "actividad": principal.get("actividad"),
            "responsable_usuario": responsable,
            "registrado_por_usuario": registrado,
            "actualizado_por_usuario": registrado,
            "fecha_registro": principal.get("fecha_registro"),
            "fecha_deteccion": principal.get("fecha_deteccion"),
            "fecha_solucion": principal.get("fecha_solucion"),
            "estado": principal.get("estado"),
            "aplica_impacto": aplica_impacto,
            "impacto_clientes": impacto,
            "impacto_tiempo": impacto,
            "impacto_soles": impacto,
            "urgencia_valor": principal.get("urgencia_valor"),
            "es_critica": principal.get("es_critica"),
            "origen_tecnologico": principal.get("origen_tecnologico"),
            "ticket_remedy": principal.get("ticket_remedy"),
            "justificacion_no_impacto": principal.get("justificacion_no_impacto"),
        }
        resultado["Hallazgos"].append(hallazgo)

        campos_tratamiento = (
            "causa_raiz", "analisis_responsable_usuario", "analisis_inicio", "analisis_fin",
            "accion_codigo", "eficacia_resultado", "pbi_numero", "fecha_cierre",
        )
        requiere_ciclo = _cadena(principal.get("estado")).upper() not in {
            "BORRADOR", "PENDIENTE_VALIDACION", "DEVUELTO", "VALIDADO", "CANCELADO"
        } or any(not _vacio(_valor_grupo(grupo, campo)) for campo in campos_tratamiento)
        if requiere_ciclo:
            fecha_cierre = _valor_grupo(grupo, "fecha_cierre")
            resultado_eficacia = _cadena(_valor_grupo(grupo, "eficacia_resultado")).upper()
            if not resultado_eficacia and _cadena(principal.get("estado")).upper() == "CERRADO":
                resultado_eficacia = "EFICAZ"
            resultado["Ciclos"].append({
                "__fila__": principal["__fila__"], "hallazgo_codigo": principal["hallazgo_codigo"],
                "ciclo_numero": 1, "motivo": "Tratamiento importado desde plantilla única",
                "creado_por_usuario": registrado, "fecha_inicio": principal.get("fecha_registro"),
                "fecha_fin": fecha_cierre, "analisis_responsable_usuario": _valor_grupo(grupo, "analisis_responsable_usuario") or responsable,
                "analisis_inicio": _valor_grupo(grupo, "analisis_inicio"), "analisis_fin": _valor_grupo(grupo, "analisis_fin"),
                "causa_raiz": _valor_grupo(grupo, "causa_raiz"),
                "cierre_responsable_usuario": _valor_grupo(grupo, "cierre_responsable") or _valor_grupo(grupo, "eficacia_evaluador"),
                "fecha_cierre": fecha_cierre, "comentarios_cierre": _valor_grupo(grupo, "comentario_cierre"),
                "resultado_cierre": resultado_eficacia if fecha_cierre else "",
            })

        numero_accion = 0
        for fila in grupo:
            tiene_compromiso = any(
                not _vacio(fila.get(campo))
                for campo in (
                    "accion_codigo", "accion_tipo", "accion_descripcion",
                    "accion_fet_inicial", "accion_estado", "accion_avance",
                    "accion_fecha_real",
                )
            )
            if not tiene_compromiso:
                continue
            numero_accion += 1
            accion_codigo = fila.get("accion_codigo") or (
                f"{principal['hallazgo_codigo']}-A{numero_accion:02d}"
            )
            accion_descripcion = fila.get("accion_descripcion")
            accion_estado = _cadena(fila.get("accion_estado")).upper() or "PENDIENTE"
            accion_avance = fila.get("accion_avance")
            if _vacio(accion_avance):
                accion_avance = 100 if accion_estado == "COMPLETADA" else 1 if accion_estado == "EN_PROCESO" else 0
            accion_inicio = fila.get("accion_fecha_inicio") or principal.get("fecha_registro")
            resultado["Compromisos"].append({
                "__fila__": fila["__fila__"], "hallazgo_codigo": principal["hallazgo_codigo"], "ciclo_numero": 1,
                "accion_codigo": accion_codigo, "tipo": fila.get("accion_tipo"),
                "descripcion": accion_descripcion, "responsable_usuario": fila.get("accion_responsable") or responsable,
                "fecha_inicio": accion_inicio, "fet_inicial": fila.get("accion_fet_inicial"),
                "fecha_vigente": fila.get("accion_fecha_vigente") or fila.get("accion_fet_inicial"),
                "fecha_real": fila.get("accion_fecha_real"), "estado": accion_estado,
                "porcentaje_avance": accion_avance, "resultado_esperado": fila.get("accion_resultado") or accion_descripcion,
                "comentario": fila.get("accion_comentario"),
            })
            fecha_evento = fila.get("accion_fecha_real") or accion_inicio
            resultado["Seguimientos"].append({
                "__fila__": fila["__fila__"], "accion_codigo": accion_codigo, "seguimiento_numero": 1,
                "usuario": fila.get("accion_responsable") or responsable, "fecha_hora": fecha_evento,
                "estado": accion_estado, "porcentaje_avance": accion_avance,
                "fecha_real": fila.get("accion_fecha_real"), "comentario": fila.get("accion_comentario"),
            })
            if not _vacio(fila.get("reprogramacion_fecha")) or not _vacio(fila.get("reprogramacion_motivo")):
                resultado["Reprogramaciones"].append({
                    "__fila__": fila["__fila__"], "accion_codigo": fila.get("accion_codigo"), "reprogramacion_numero": 1,
                    "usuario": fila.get("accion_responsable") or responsable, "fecha_hora": fila.get("reprogramacion_fecha"),
                    "fecha_anterior": fila.get("accion_fet_inicial"), "nueva_fecha": fila.get("accion_fecha_vigente"),
                    "motivo": fila.get("reprogramacion_motivo"),
                })

        eficacia = _valor_grupo(grupo, "eficacia_resultado")
        if _vacio(eficacia) and _cadena(principal.get("estado")).upper() == "CERRADO":
            eficacia = "EFICAZ"
        if not _vacio(eficacia):
            fecha_evaluacion = _valor_grupo(grupo, "eficacia_fecha")
            resultado["Evaluaciones"].append({
                "__fila__": principal["__fila__"], "hallazgo_codigo": principal["hallazgo_codigo"], "ciclo_numero": 1,
                "evaluacion_numero": 1, "evaluador_usuario": _valor_grupo(grupo, "eficacia_evaluador"),
                "fecha_evaluacion": fecha_evaluacion, "resultado": eficacia,
                "comentario": _valor_grupo(grupo, "eficacia_comentario") or "Evaluación eficaz importada desde la carga masiva.",
                "fecha_registro": fecha_evaluacion,
            })

        numero_pbi = _valor_grupo(grupo, "pbi_numero")
        if not _vacio(numero_pbi):
            resultado["PBI"].append({
                "__fila__": principal["__fila__"], "hallazgo_codigo": principal["hallazgo_codigo"], "ciclo_numero": 1,
                "numero_pbi": numero_pbi, "sistema": _valor_grupo(grupo, "pbi_sistema"),
                "responsable_ti_usuario": _valor_grupo(grupo, "pbi_responsable"), "estado": _valor_grupo(grupo, "pbi_estado"),
                "fecha_creacion": _valor_grupo(grupo, "pbi_fecha_creacion"), "fecha_cierre": _valor_grupo(grupo, "pbi_fecha_cierre"),
            })

        rutas = [ruta.strip().replace("\\", "/") for ruta in _cadena(_valor_grupo(grupo, "evidencias_rutas")).split(";") if ruta.strip()]
        for ruta in rutas:
            resultado["Evidencias"].append({
                "__fila__": principal["__fila__"], "hallazgo_codigo": principal["hallazgo_codigo"], "contexto": "HALLAZGO",
                "archivo_ruta": ruta, "descripcion": _valor_grupo(grupo, "evidencias_descripcion"),
                "subido_por_usuario": _valor_grupo(grupo, "evidencias_usuario") or responsable,
                "fecha_carga": _valor_grupo(grupo, "evidencias_fecha") or principal.get("fecha_registro"),
            })
    return resultado


class ImportadorMasivo:
    def __init__(self, *, hojas, archivos=None, ejecutado_por):
        self.hojas = convertir_hoja_unica(hojas)
        self.archivos = archivos or {}
        self.ejecutado_por = ejecutado_por
        self.errores = []
        self.preparados = defaultdict(list)
        self._cargar_maestros()

    def error(self, hoja, fila, mensaje):
        self.errores.append(f"{hoja}, fila {fila}: {mensaje}")

    def _cargar_maestros(self):
        usuarios = list(Usuario.objects.filter(is_active=True))
        self.usuarios = {}
        for usuario in usuarios:
            self.usuarios[usuario.username.casefold()] = usuario
            if usuario.email:
                self.usuarios[usuario.email.casefold()] = usuario
        self.procesos = {p.nombre.casefold(): p for p in Proceso.objects.all()}
        self.subprocesos = {(s.proceso_id, s.nombre.casefold()): s for s in Subproceso.objects.all()}
        catalogos = list(Catalogo.objects.all())
        self.catalogos = {(c.clase, c.codigo.casefold()): c for c in catalogos}
        self.catalogos_valor = {(c.clase, c.valor): c for c in catalogos if c.valor is not None}
        self.preguntas = {p.codigo.casefold(): p for p in PreguntaCausa.objects.select_related("categoria")}
        self.matriz = {(m.impacto.valor, m.urgencia_id): m.prioridad for m in MatrizPrioridad.objects.filter(activo=True).select_related("impacto", "prioridad")}

    def usuario(self, valor, etiqueta):
        usuario = self.usuarios.get(_cadena(valor).casefold())
        if not usuario:
            raise ValueError(f"{etiqueta}: el usuario activo '{_cadena(valor)}' no existe")
        return usuario

    def preparar(self):
        if "Hallazgos" not in self.hojas:
            raise ErrorCargaMasiva(["Falta la hoja Hallazgos."])
        for hoja, requeridas in REQUERIDAS.items():
            if hoja not in self.hojas:
                self.hojas[hoja] = []
                continue
            filas = self.hojas[hoja]
            if filas:
                faltan = requeridas - set(filas[0])
                if faltan:
                    self.errores.append(f"{hoja}: faltan columnas requeridas: {', '.join(sorted(faltan))}.")
        if not self.hojas["Hallazgos"]:
            self.errores.append("Hallazgos: registre al menos un hallazgo para validar o importar.")
        self._preparar_hallazgos()
        self._preparar_ciclos()
        self._preparar_respuestas()
        self._preparar_acciones()
        self._preparar_seguimientos()
        self._preparar_reprogramaciones()
        self._preparar_evaluaciones()
        self._preparar_comunicaciones()
        self._preparar_pbis()
        self._preparar_evidencias()
        self._validar_coherencia()
        if self.errores:
            raise ErrorCargaMasiva(self.errores)
        return self

    def _preparar_hallazgos(self):
        vistos = set()
        existentes = {c.casefold() for c in Hallazgo.objects.values_list("codigo", flat=True)}
        estados = dict(Hallazgo._meta.get_field("estado").choices)
        for fila in self.hojas["Hallazgos"]:
            n = fila.get("__fila__", "?")
            try:
                codigo = _cadena(fila.get("hallazgo_codigo"))
                if not codigo:
                    raise ValueError("hallazgo_codigo es obligatorio")
                clave = codigo.casefold()
                if clave in vistos:
                    raise ValueError(f"hallazgo_codigo duplicado: {codigo}")
                if clave in existentes:
                    raise ValueError(f"el hallazgo {codigo} ya existe; la carga solo crea registros nuevos")
                vistos.add(clave)
                tipo = self.catalogos.get(("TIPO", _cadena(fila.get("tipo_codigo")).casefold()))
                if not tipo:
                    raise ValueError("tipo_codigo no existe en el catálogo TIPO")
                fuente_codigo = _cadena(fila.get("fuente_codigo"))
                fuente = self.catalogos.get(("FUENTE", fuente_codigo.casefold())) if fuente_codigo else None
                if fuente_codigo and not fuente:
                    raise ValueError("fuente_codigo no existe en el catálogo FUENTE")
                proceso = self.procesos.get(_cadena(fila.get("proceso")).casefold())
                if not proceso:
                    raise ValueError("el proceso no existe")
                subnombre = _cadena(fila.get("subproceso"))
                subproceso = self.subprocesos.get((proceso.pk, subnombre.casefold())) if subnombre else None
                if subnombre and not subproceso:
                    raise ValueError("el subproceso no existe dentro del proceso indicado")
                estado = _cadena(fila.get("estado")).upper()
                if estado not in estados:
                    raise ValueError("estado de hallazgo no válido")
                aplica = _si_no(fila.get("aplica_impacto"), "aplica_impacto", predeterminado="SI") == "SI"
                impactos = [_entero(fila.get(c), c, minimo=1, maximo=3, requerido=aplica) for c in ("impacto_clientes", "impacto_tiempo", "impacto_soles")]
                urgencia_valor = _entero(fila.get("urgencia_valor"), "urgencia_valor", minimo=1, maximo=3, requerido=aplica)
                urgencia = self.catalogos_valor.get(("URGENCIA", urgencia_valor)) if urgencia_valor else None
                if urgencia_valor and not urgencia:
                    raise ValueError("urgencia_valor no existe en el catálogo URGENCIA")
                prioridad_codigo = _cadena(fila.get("prioridad_codigo"))
                prioridad = self.catalogos.get(("PRIORIDAD", prioridad_codigo.casefold())) if prioridad_codigo else None
                impacto_resultante = max(impactos) if aplica else None
                if aplica and prioridad is None:
                    prioridad = self.matriz.get((impacto_resultante, urgencia.pk))
                if aplica and prioridad is None:
                    raise ValueError("no existe prioridad para la combinación de impacto y urgencia")
                es_critica = _si_no(fila.get("es_critica"), "es_critica", permite_na=True, predeterminado="SI" if prioridad and prioridad.codigo == "CRITICA" else "NO")
                origen = _si_no(fila.get("origen_tecnologico"), "origen_tecnologico", predeterminado="NO") == "SI"
                justificacion = _cadena(fila.get("justificacion_no_impacto"))
                if not aplica and not justificacion:
                    justificacion = "Registro histórico importado sin evaluación de impacto."
                registrado = self.usuario(fila.get("registrado_por_usuario"), "registrado_por_usuario")
                actualizado = self.usuario(fila.get("actualizado_por_usuario") or registrado.username, "actualizado_por_usuario")
                datos = dict(
                    codigo=codigo, titulo=_cadena(fila.get("titulo")), tipo_registro=tipo,
                    fuente_deteccion=fuente, proceso=proceso, subproceso=subproceso,
                    actividad=_cadena(fila.get("actividad")), descripcion=_cadena(fila.get("descripcion")),
                    ticket_remedy=_cadena(fila.get("ticket_remedy")),
                    responsable=self.usuario(fila.get("responsable_usuario"), "responsable_usuario"),
                    registrado_por=registrado,
                    fecha_deteccion=_fecha(fila.get("fecha_deteccion"), "fecha_deteccion", hora=True),
                    fecha_registro=_fecha(fila.get("fecha_registro"), "fecha_registro", hora=True, requerido=True),
                    fecha_solucion=_fecha(fila.get("fecha_solucion"), "fecha_solucion"),
                    impacto_clientes=impactos[0], impacto_tiempo=impactos[1], impacto_soles=impactos[2],
                    impacto_resultante=impacto_resultante, urgencia=urgencia, prioridad=prioridad,
                    aplica_impacto=aplica, justificacion_no_impacto=justificacion,
                    es_critica=es_critica, origen_tecnologico=origen,
                    criterio_categoria=_cadena(fila.get("criterio_categoria")),
                    requisito_referencia=_cadena(fila.get("requisito_referencia")),
                    estado=estado, updated_by=actualizado,
                )
                if not datos["titulo"]:
                    raise ValueError("titulo es obligatorio")
                if aplica:
                    selecciones = ImpactoService.selecciones(clientes=impactos[0], tiempo=impactos[1], soles=impactos[2])
                    datos.update(selecciones)
                    datos["urgencia_seleccion"], datos["urgencia_area"] = UrgenciaService.seleccion(area=registrado.area, urgencia=urgencia)
                    datos["prioridad_snapshot"] = prioridad.nombre
                else:
                    datos["impacto_clientes"] = datos["impacto_tiempo"] = datos["impacto_soles"] = None
                    datos["urgencia"] = datos["prioridad"] = None
                    datos["prioridad_snapshot"] = "No aplica: " + justificacion[:150]
                self.preparados["hallazgos"].append(datos)
            except (ValueError, ValidationError) as exc:
                self.error("Hallazgos", n, "; ".join(getattr(exc, "messages", [str(exc)])))

    def _preparar_ciclos(self):
        vistos = set()
        for fila in self.hojas["Ciclos"]:
            n = fila.get("__fila__", "?")
            try:
                codigo = _cadena(fila.get("hallazgo_codigo"))
                numero = _entero(fila.get("ciclo_numero"), "ciclo_numero", minimo=1, requerido=True)
                clave = (codigo.casefold(), numero)
                if clave in vistos:
                    raise ValueError("ciclo duplicado")
                vistos.add(clave)
                control = {}
                tipos = [t.strip().upper() for t in re.split(r"[,;]", _cadena(fila.get("control_tipos"))) if t.strip()]
                if tipos or any(not _vacio(fila.get(c)) for c in ("control_nombre","control_descripcion","control_mitiga_riesgo","control_frecuencia","control_responsable","control_evidencia")):
                    if not set(tipos) <= {"PREVENTIVO", "DETECTIVO", "CORRECTIVO"}:
                        raise ValueError("control_tipos solo admite PREVENTIVO, DETECTIVO y CORRECTIVO")
                    control = {"tipos": tipos, "nombre": _cadena(fila.get("control_nombre")), "descripcion": _cadena(fila.get("control_descripcion")), "mitiga_riesgo": _si_no(fila.get("control_mitiga_riesgo"), "control_mitiga_riesgo", permite_na=True), "frecuencia": _cadena(fila.get("control_frecuencia")), "responsable": _cadena(fila.get("control_responsable")), "evidencia": _cadena(fila.get("control_evidencia"))}
                self.preparados["ciclos"].append(dict(
                    clave=clave, codigo=codigo, numero=numero, motivo=_cadena(fila.get("motivo")),
                    creado_por=self.usuario(fila.get("creado_por_usuario"), "creado_por_usuario"),
                    fecha_inicio=_fecha(fila.get("fecha_inicio"), "fecha_inicio", hora=True, requerido=True),
                    fecha_fin=_fecha(fila.get("fecha_fin"), "fecha_fin", hora=True),
                    analisis_responsable=self.usuario(fila.get("analisis_responsable_usuario"), "analisis_responsable_usuario") if not _vacio(fila.get("analisis_responsable_usuario")) else None,
                    analisis_inicio=_fecha(fila.get("analisis_inicio"), "analisis_inicio", hora=True),
                    analisis_fin=_fecha(fila.get("analisis_fin"), "analisis_fin", hora=True),
                    causa_raiz=_cadena(fila.get("causa_raiz")), control=control,
                    responsable_cierre=self.usuario(fila.get("cierre_responsable_usuario"), "cierre_responsable_usuario") if not _vacio(fila.get("cierre_responsable_usuario")) else None,
                    fecha_cierre=_fecha(fila.get("fecha_cierre"), "fecha_cierre", hora=True),
                    comentarios_cierre=_cadena(fila.get("comentarios_cierre")), resultado_cierre=_cadena(fila.get("resultado_cierre")).upper(),
                ))
            except (ValueError, ValidationError) as exc:
                self.error("Ciclos", n, "; ".join(getattr(exc, "messages", [str(exc)])))

    def _preparar_respuestas(self):
        vistos = set()
        for fila in self.hojas["Respuestas_6M"]:
            n = fila.get("__fila__", "?")
            try:
                codigo = _cadena(fila.get("hallazgo_codigo")); ciclo = _entero(fila.get("ciclo_numero"), "ciclo_numero", minimo=1, requerido=True)
                pregunta = self.preguntas.get(_cadena(fila.get("pregunta_codigo")).casefold())
                if not pregunta:
                    raise ValueError("pregunta_codigo no existe")
                clave = (codigo.casefold(), ciclo, pregunta.codigo.casefold())
                if clave in vistos:
                    raise ValueError("respuesta duplicada para la misma pregunta")
                vistos.add(clave)
                self.preparados["respuestas"].append(dict(clave_ciclo=(codigo.casefold(), ciclo), pregunta=pregunta,
                    texto=_cadena(fila.get("texto_personalizado")) or pregunta.texto,
                    respuesta=_si_no(fila.get("respuesta"), "respuesta", permite_na=True), comentario=_cadena(fila.get("comentario")),
                    usuario=self.usuario(fila.get("usuario"), "usuario"), fecha=_fecha(fila.get("fecha_hora"), "fecha_hora", hora=True, requerido=True)))
            except (ValueError, ValidationError) as exc:
                self.error("Respuestas_6M", n, "; ".join(getattr(exc, "messages", [str(exc)])))

    def _preparar_acciones(self):
        vistos = set()
        for fila in self.hojas["Compromisos"]:
            n = fila.get("__fila__", "?")
            try:
                codigo_h = _cadena(fila.get("hallazgo_codigo")); ciclo = _entero(fila.get("ciclo_numero"), "ciclo_numero", minimo=1, requerido=True)
                codigo = _cadena(fila.get("accion_codigo")); clave = codigo.casefold()
                if not codigo or clave in vistos or Accion.objects.filter(codigo__iexact=codigo).exists():
                    raise ValueError("accion_codigo está vacío, duplicado o ya existe")
                vistos.add(clave)
                tipo = _cadena(fila.get("tipo")).upper(); estado = _cadena(fila.get("estado")).upper()
                if tipo not in {"INMEDIATA", "ACCION_INMEDIATA", "CORRECTIVA"}: raise ValueError("tipo debe ser INMEDIATA, ACCION_INMEDIATA o CORRECTIVA")
                if estado not in dict(Accion.ESTADOS): raise ValueError("estado de compromiso no válido")
                avance = _entero(fila.get("porcentaje_avance"), "porcentaje_avance", minimo=0, maximo=100, requerido=True)
                fecha_inicio = _fecha(fila.get("fecha_inicio"), "fecha_inicio", requerido=True)
                fet = _fecha(fila.get("fet_inicial"), "fet_inicial", requerido=True); vigente = _fecha(fila.get("fecha_vigente"), "fecha_vigente", requerido=True)
                real = _fecha(fila.get("fecha_real"), "fecha_real")
                if fet < fecha_inicio or vigente < fecha_inicio: raise ValueError("las fechas de compromiso no pueden ser anteriores al inicio")
                if estado == "COMPLETADA" and (avance != 100 or real is None): raise ValueError("un compromiso COMPLETADA requiere 100% y fecha_real")
                if estado != "COMPLETADA" and (avance >= 100 or real is not None): raise ValueError("un compromiso no completado requiere avance menor a 100 y sin fecha_real")
                if estado in {"PENDIENTE", "CANCELADA"} and avance != 0: raise ValueError("un compromiso pendiente o cancelado requiere 0%")
                self.preparados["acciones"].append(dict(clave=clave, codigo=codigo, clave_ciclo=(codigo_h.casefold(), ciclo), tipo=tipo,
                    descripcion=_cadena(fila.get("descripcion")), responsable=self.usuario(fila.get("responsable_usuario"), "responsable_usuario"),
                    fecha_inicio=fecha_inicio, fet_inicial=fet, fecha_vigente=vigente, fecha_real=real,
                    estado=estado, porcentaje_avance=avance, resultado_esperado=_cadena(fila.get("resultado_esperado")), comentario=_cadena(fila.get("comentario"))))
            except (ValueError, ValidationError) as exc:
                self.error("Compromisos", n, "; ".join(getattr(exc, "messages", [str(exc)])))

    def _preparar_seguimientos(self):
        self._preparar_eventos_accion("Seguimientos", "seguimientos", "seguimiento_numero")

    def _preparar_reprogramaciones(self):
        self._preparar_eventos_accion("Reprogramaciones", "reprogramaciones", "reprogramacion_numero")

    def _preparar_eventos_accion(self, hoja, destino, campo_numero):
        vistos = set()
        for fila in self.hojas[hoja]:
            n = fila.get("__fila__", "?")
            try:
                accion = _cadena(fila.get("accion_codigo")); numero = _entero(fila.get(campo_numero), campo_numero, minimo=1, requerido=True)
                clave = (accion.casefold(), numero)
                if clave in vistos: raise ValueError("número duplicado para el mismo compromiso")
                vistos.add(clave)
                base = dict(accion=accion.casefold(), numero=numero, usuario=self.usuario(fila.get("usuario"), "usuario"), fecha=_fecha(fila.get("fecha_hora"), "fecha_hora", hora=True, requerido=True))
                if hoja == "Seguimientos":
                    estado = _cadena(fila.get("estado")).upper()
                    if estado not in dict(Accion.ESTADOS): raise ValueError("estado no válido")
                    base.update(estado=estado, avance=_entero(fila.get("porcentaje_avance"), "porcentaje_avance", minimo=0, maximo=100, requerido=True), fecha_real=_fecha(fila.get("fecha_real"), "fecha_real"), comentario=_cadena(fila.get("comentario")))
                else:
                    base.update(fecha_anterior=_fecha(fila.get("fecha_anterior"), "fecha_anterior", requerido=True), nueva_fecha=_fecha(fila.get("nueva_fecha"), "nueva_fecha", requerido=True), motivo=_cadena(fila.get("motivo")))
                self.preparados[destino].append(base)
            except (ValueError, ValidationError) as exc:
                self.error(hoja, n, "; ".join(getattr(exc, "messages", [str(exc)])))

    def _preparar_evaluaciones(self):
        vistos = set()
        for fila in self.hojas["Evaluaciones"]:
            n = fila.get("__fila__", "?")
            try:
                codigo = _cadena(fila.get("hallazgo_codigo")); ciclo = _entero(fila.get("ciclo_numero"), "ciclo_numero", minimo=1, requerido=True); numero = _entero(fila.get("evaluacion_numero"), "evaluacion_numero", minimo=1, requerido=True)
                clave = (codigo.casefold(), ciclo, numero)
                if clave in vistos: raise ValueError("evaluacion_numero duplicado")
                vistos.add(clave); resultado = _cadena(fila.get("resultado")).upper()
                if resultado not in dict(EvaluacionEficacia.RESULTADOS): raise ValueError("resultado debe ser EFICAZ o NO_EFICAZ")
                self.preparados["evaluaciones"].append(dict(clave=clave, clave_ciclo=(codigo.casefold(), ciclo), numero=numero, evaluador=self.usuario(fila.get("evaluador_usuario"), "evaluador_usuario"), fecha_evaluacion=_fecha(fila.get("fecha_evaluacion"), "fecha_evaluacion", requerido=True), resultado=resultado, comentario=_cadena(fila.get("comentario")), fecha_registro=_fecha(fila.get("fecha_registro"), "fecha_registro", hora=True, requerido=True)))
            except (ValueError, ValidationError) as exc:
                self.error("Evaluaciones", n, "; ".join(getattr(exc, "messages", [str(exc)])))

    def _preparar_comunicaciones(self):
        for fila in self.hojas["Comunicaciones"]:
            n = fila.get("__fila__", "?")
            try:
                codigo = _cadena(fila.get("hallazgo_codigo")); ciclo = _entero(fila.get("ciclo_numero"), "ciclo_numero", minimo=1, requerido=True)
                self.preparados["comunicaciones"].append(dict(clave_ciclo=(codigo.casefold(), ciclo), registrado_por=self.usuario(fila.get("registrado_por_usuario"), "registrado_por_usuario"), destinatarios=_cadena(fila.get("destinatarios")), medio=_cadena(fila.get("medio")), descripcion=_cadena(fila.get("descripcion")), fecha=_fecha(fila.get("fecha"), "fecha", hora=True, requerido=True)))
            except (ValueError, ValidationError) as exc:
                self.error("Comunicaciones", n, "; ".join(getattr(exc, "messages", [str(exc)])))

    def _preparar_pbis(self):
        vistos = set()
        for fila in self.hojas["PBI"]:
            n = fila.get("__fila__", "?")
            try:
                codigo = _cadena(fila.get("hallazgo_codigo")); ciclo = _entero(fila.get("ciclo_numero"), "ciclo_numero", minimo=1, requerido=True); numero = _cadena(fila.get("numero_pbi")); clave = (codigo.casefold(), ciclo, numero.casefold())
                if clave in vistos: raise ValueError("numero_pbi duplicado en el ciclo")
                vistos.add(clave); estado = _cadena(fila.get("estado")).upper(); cierre = _fecha(fila.get("fecha_cierre"), "fecha_cierre")
                if estado not in {"ABIERTO", "CERRADO"}: raise ValueError("estado PBI no válido")
                if (estado == "CERRADO") != (cierre is not None): raise ValueError("PBI cerrado requiere fecha_cierre y PBI abierto no debe tenerla")
                self.preparados["pbis"].append(dict(clave_ciclo=(codigo.casefold(), ciclo), numero_pbi=numero, ticket_incidente=_cadena(fila.get("ticket_incidente")), sistema=_cadena(fila.get("sistema")), herramienta=_cadena(fila.get("herramienta")) or "Helix (registro manual)", responsable_ti=self.usuario(fila.get("responsable_ti_usuario"), "responsable_ti_usuario"), estado=estado, fecha_creacion=_fecha(fila.get("fecha_creacion"), "fecha_creacion", hora=True, requerido=True), fecha_cierre=cierre, observacion=_cadena(fila.get("observacion"))))
            except (ValueError, ValidationError) as exc:
                self.error("PBI", n, "; ".join(getattr(exc, "messages", [str(exc)])))

    def _preparar_evidencias(self):
        vistos = set()
        permitidos = {"HALLAZGO","ANALISIS","ACCION","EVALUACION","CIERRE"}
        for fila in self.hojas["Evidencias"]:
            n = fila.get("__fila__", "?")
            try:
                codigo = _cadena(fila.get("hallazgo_codigo")); ciclo = _entero(fila.get("ciclo_numero"), "ciclo_numero", minimo=1) ; contexto = _cadena(fila.get("contexto")).upper(); referencia = _cadena(fila.get("referencia_contexto")); ruta = _cadena(fila.get("archivo_ruta")).replace("\\", "/")
                if contexto not in permitidos: raise ValueError("contexto no válido")
                if contexto != "HALLAZGO" and ciclo is None: raise ValueError("ciclo_numero es obligatorio para este contexto")
                if contexto in {"ACCION","EVALUACION"} and not referencia: raise ValueError("referencia_contexto es obligatoria")
                if ruta in vistos: raise ValueError("archivo_ruta duplicada")
                vistos.add(ruta)
                if ruta not in self.archivos: raise ValueError(f"el archivo '{ruta}' no está dentro del ZIP")
                subida = SimpleUploadedFile(Path(ruta).name, self.archivos[ruta])
                mime = validar_archivo(subida)
                self.preparados["evidencias"].append(dict(codigo=codigo.casefold(), ciclo=ciclo, contexto=contexto, referencia=referencia, ruta=ruta, contenido=self.archivos[ruta], mime=mime, descripcion=_cadena(fila.get("descripcion")), subido_por=self.usuario(fila.get("subido_por_usuario"), "subido_por_usuario"), fecha_carga=_fecha(fila.get("fecha_carga"), "fecha_carga", hora=True, requerido=True)))
            except (ValueError, ValidationError) as exc:
                self.error("Evidencias", n, "; ".join(getattr(exc, "messages", [str(exc)])))

    def _validar_coherencia(self):
        hallazgos = {h["codigo"].casefold(): h for h in self.preparados["hallazgos"]}
        ciclos = {c["clave"]: c for c in self.preparados["ciclos"]}
        acciones = {a["clave"]: a for a in self.preparados["acciones"]}
        evaluaciones = {e["clave"]: e for e in self.preparados["evaluaciones"]}
        for c in ciclos.values():
            if c["clave"][0] not in hallazgos: self.errores.append(f"Ciclos: {c['codigo']} no existe en Hallazgos.")
        for grupo in ("respuestas","acciones","evaluaciones","comunicaciones","pbis"):
            for item in self.preparados[grupo]:
                if item["clave_ciclo"] not in ciclos: self.errores.append(f"{grupo}: no existe el ciclo {item['clave_ciclo']}.")
        for grupo in ("seguimientos","reprogramaciones"):
            for item in self.preparados[grupo]:
                if item["accion"] not in acciones: self.errores.append(f"{grupo}: no existe el compromiso {item['accion']}.")
        seguimientos_por_accion = defaultdict(list)
        for item in self.preparados["seguimientos"]:
            seguimientos_por_accion[item["accion"]].append(item)
            if item["estado"] == "COMPLETADA" and (item["avance"] != 100 or item["fecha_real"] is None):
                self.errores.append(f"Seguimientos: {item['accion']} COMPLETADA requiere 100% y fecha_real.")
            if item["estado"] != "COMPLETADA" and (item["avance"] >= 100 or item["fecha_real"] is not None):
                self.errores.append(f"Seguimientos: {item['accion']} no completada requiere avance menor a 100 y sin fecha_real.")
        for clave, items in seguimientos_por_accion.items():
            if clave not in acciones:
                continue
            ultimo = max(items, key=lambda item: item["numero"])
            accion = acciones[clave]
            if (ultimo["estado"], ultimo["avance"], ultimo["fecha_real"]) != (accion["estado"], accion["porcentaje_avance"], accion["fecha_real"]):
                self.errores.append(f"Seguimientos: el último seguimiento de {accion['codigo']} no coincide con su estado, avance y fecha_real en Compromisos.")
        reprogramaciones_por_accion = defaultdict(list)
        for item in self.preparados["reprogramaciones"]:
            reprogramaciones_por_accion[item["accion"]].append(item)
        for clave, items in reprogramaciones_por_accion.items():
            if len(items) > 3:
                self.errores.append(f"Reprogramaciones: {clave} supera el máximo de tres.")
            if clave in acciones:
                ultimo = max(items, key=lambda item: item["numero"])
                if ultimo["nueva_fecha"] != acciones[clave]["fecha_vigente"]:
                    self.errores.append(f"Reprogramaciones: la última nueva_fecha de {acciones[clave]['codigo']} debe coincidir con fecha_vigente en Compromisos.")
        ciclos_por_hallazgo = defaultdict(list)
        for c in ciclos.values(): ciclos_por_hallazgo[c["clave"][0]].append(c)
        acciones_por_ciclo = defaultdict(list)
        for accion in acciones.values(): acciones_por_ciclo[accion["clave_ciclo"]].append(accion)
        pbis_por_ciclo = defaultdict(list)
        for pbi in self.preparados["pbis"]: pbis_por_ciclo[pbi["clave_ciclo"]].append(pbi)
        for codigo, hallazgo in hallazgos.items():
            lista = sorted(ciclos_por_hallazgo[codigo], key=lambda c: c["numero"])
            if lista and [c["numero"] for c in lista] != list(range(1, len(lista)+1)):
                self.errores.append(f"Ciclos: {hallazgo['codigo']} debe numerar sus ciclos consecutivamente desde 1.")
            if hallazgo["estado"] not in {"BORRADOR","PENDIENTE_VALIDACION","DEVUELTO","VALIDADO","CANCELADO"} and not lista:
                self.errores.append(f"Hallazgos: {hallazgo['codigo']} en estado {hallazgo['estado']} requiere al menos un ciclo.")
            if hallazgo["estado"] == "CERRADO":
                if not lista or not lista[-1]["fecha_cierre"] or lista[-1]["resultado_cierre"] != "EFICAZ":
                    self.errores.append(f"Hallazgos: {hallazgo['codigo']} cerrado requiere fecha_cierre y resultado_cierre EFICAZ en su último ciclo.")
                tiene_eficaz = bool(lista) and any(
                    e["clave_ciclo"] == (codigo, lista[-1]["numero"])
                    and e["resultado"] == "EFICAZ"
                    for e in evaluaciones.values()
                )
                if not tiene_eficaz:
                    self.errores.append(f"Evaluaciones: {hallazgo['codigo']} cerrado requiere una evaluación EFICAZ en su último ciclo.")
                if lista:
                    acciones_actuales = acciones_por_ciclo[(codigo, lista[-1]["numero"])]
                    vigentes = [a for a in acciones_actuales if a["estado"] != "CANCELADA"]
                    if not vigentes or any(a["estado"] != "COMPLETADA" or a["porcentaje_avance"] != 100 for a in vigentes):
                        self.errores.append(f"Compromisos: {hallazgo['codigo']} cerrado requiere todos sus compromisos vigentes completados al 100%.")
                    if not any(a["tipo"] == "INMEDIATA" and a["estado"] == "COMPLETADA" for a in vigentes):
                        self.errores.append(f"Compromisos: {hallazgo['codigo']} cerrado requiere una solución inmediata completada.")
                    if hallazgo["es_critica"] == "SI":
                        if not lista[-1]["analisis_fin"]:
                            self.errores.append(f"Ciclos: {hallazgo['codigo']} crítico y cerrado requiere análisis finalizado.")
                        if not any(a["tipo"] == "CORRECTIVA" and a["estado"] == "COMPLETADA" for a in vigentes):
                            self.errores.append(f"Compromisos: {hallazgo['codigo']} crítico y cerrado requiere una acción correctiva completada.")
                        if hallazgo["origen_tecnologico"] and not pbis_por_ciclo[(codigo, lista[-1]["numero"])]:
                            self.errores.append(f"PBI: {hallazgo['codigo']} crítico tecnológico requiere al menos una referencia PBI.")
        for evidencia in self.preparados["evidencias"]:
            if evidencia["codigo"] not in hallazgos: self.errores.append(f"Evidencias: el hallazgo {evidencia['codigo']} no existe.")
            clave_ciclo = (evidencia["codigo"], evidencia["ciclo"])
            if evidencia["contexto"] != "HALLAZGO" and clave_ciclo not in ciclos: self.errores.append(f"Evidencias: no existe el ciclo {clave_ciclo}.")
            if evidencia["contexto"] == "ACCION" and evidencia["referencia"].casefold() not in acciones: self.errores.append(f"Evidencias: no existe el compromiso {evidencia['referencia']}.")
            if evidencia["contexto"] == "EVALUACION":
                try: numero = int(evidencia["referencia"])
                except ValueError: numero = -1
                if (evidencia["codigo"], evidencia["ciclo"], numero) not in evaluaciones: self.errores.append(f"Evidencias: no existe la evaluación {evidencia['referencia']}.")

    @transaction.atomic
    def guardar(self):
        hallazgos = {}
        for datos in self.preparados["hallazgos"]:
            h = Hallazgo(**datos)
            h.full_clean()
            h.save(force_insert=True)
            hallazgos[h.codigo.casefold()] = h
            HistorialHallazgo.objects.create(hallazgo=h, usuario=self.ejecutado_por, fecha_hora=h.fecha_registro, accion="IMPORTACION_MASIVA", estado_anterior="", estado_nuevo=h.estado, comentario="Expediente creado mediante carga masiva.", metadata_json={"origen": "plantilla_xlsx"})
            self._actualizar_correlativo(h)
        ciclos = {}
        for datos in self.preparados["ciclos"]:
            clave = datos.pop("clave"); codigo = datos.pop("codigo")
            ciclo = CicloTratamiento(hallazgo=hallazgos[codigo.casefold()], **datos)
            ciclo.full_clean(); ciclo.save(force_insert=True); ciclos[clave] = ciclo
            if ciclo.analisis_fin:
                HistorialHallazgo.objects.create(hallazgo=ciclo.hallazgo, usuario=ciclo.analisis_responsable or ciclo.creado_por, fecha_hora=ciclo.analisis_fin, accion="FINALIZAR_ANALISIS", estado_anterior=ciclo.hallazgo.estado, estado_nuevo=ciclo.hallazgo.estado, comentario=ciclo.causa_raiz, metadata_json={"analisis": ciclo.pk, "ciclo": ciclo.numero, "origen": "carga_masiva"})
        respuestas = defaultdict(list)
        for item in self.preparados["respuestas"]: respuestas[item["clave_ciclo"]].append(item)
        for clave, items in respuestas.items():
            ciclo = ciclos[clave]
            preguntas = list(PreguntaCausa.objects.filter(activo=True, categoria__activo=True).order_by("categoria__orden", "orden"))
            ciclo.checklist_snapshot = [{"id": p.pk, "codigo": p.codigo, "texto": p.texto, "es_otro": p.texto.strip().rstrip(":").casefold() == "otro"} for p in preguntas]
            ciclo.respuestas = [{"pregunta_id": x["pregunta"].pk, "codigo_snapshot": x["pregunta"].codigo, "texto_snapshot": x["texto"], "es_otro": x["pregunta"].texto.strip().rstrip(":").casefold() == "otro", "respuesta": x["respuesta"], "comentario": x["comentario"], "usuario_id": x["usuario"].pk, "fecha": x["fecha"].isoformat()} for x in items]
            ciclo.save(update_fields=["checklist_snapshot","respuestas"])
        acciones = {}
        for datos in self.preparados["acciones"]:
            clave = datos.pop("clave"); clave_ciclo = datos.pop("clave_ciclo")
            accion = Accion(ciclo=ciclos[clave_ciclo], **datos); accion.full_clean(); accion.save(force_insert=True); acciones[clave] = accion
            fecha_evento = timezone.make_aware(datetime.combine(accion.fecha_inicio, time.min))
            HistorialHallazgo.objects.create(hallazgo=accion.hallazgo, usuario=accion.responsable, fecha_hora=fecha_evento, accion="CREAR_ACCION", accion_relacionada=accion, estado_anterior=accion.hallazgo.estado, estado_nuevo=accion.hallazgo.estado, metadata_json={"accion": accion.codigo, "tipo": accion.tipo, "ciclo": accion.ciclo.numero, "origen": "carga_masiva"})
        for item in self.preparados["seguimientos"]:
            accion = acciones[item["accion"]]
            HistorialHallazgo.objects.create(hallazgo=accion.hallazgo, usuario=item["usuario"], fecha_hora=item["fecha"], accion="SEGUIMIENTO_ACCION", accion_relacionada=accion, estado_anterior=accion.hallazgo.estado, estado_nuevo=accion.hallazgo.estado, comentario=item["comentario"], metadata_json={"accion": accion.codigo, "numero": item["numero"], "estado": item["estado"], "avance": item["avance"], "fecha_real": str(item["fecha_real"] or "")})
        for item in self.preparados["reprogramaciones"]:
            accion = acciones[item["accion"]]
            HistorialHallazgo.objects.create(hallazgo=accion.hallazgo, usuario=item["usuario"], fecha_hora=item["fecha"], accion="REPROGRAMACION", accion_relacionada=accion, estado_anterior=accion.hallazgo.estado, estado_nuevo=accion.hallazgo.estado, comentario=item["motivo"], metadata_json={"accion": accion.codigo, "numero": item["numero"], "fecha_anterior": str(item["fecha_anterior"]), "nueva_fecha": str(item["nueva_fecha"])})
        evaluaciones = {}
        for datos in self.preparados["evaluaciones"]:
            clave = datos.pop("clave"); clave_ciclo = datos.pop("clave_ciclo"); numero = datos.pop("numero"); fecha_registro = datos.pop("fecha_registro")
            evaluacion = EvaluacionEficacia(ciclo=ciclos[clave_ciclo], fecha_registro=fecha_registro, **datos); evaluacion.full_clean(); evaluacion.save(force_insert=True); evaluaciones[clave] = evaluacion
            HistorialHallazgo.objects.create(hallazgo=evaluacion.ciclo.hallazgo, usuario=evaluacion.evaluador, fecha_hora=fecha_registro, accion="EVALUACION_EFICACIA", estado_anterior=evaluacion.ciclo.hallazgo.estado, estado_nuevo=evaluacion.ciclo.hallazgo.estado, comentario=evaluacion.comentario, metadata_json={"resultado": evaluacion.resultado, "ciclo": evaluacion.ciclo.numero, "evaluacion": evaluacion.pk, "numero_importado": numero})
        for datos in self.preparados["comunicaciones"]:
            clave_ciclo = datos.pop("clave_ciclo"); comunicacion = ComunicacionHallazgo(ciclo=ciclos[clave_ciclo], **datos); comunicacion.full_clean(); comunicacion.save(force_insert=True)
            HistorialHallazgo.objects.create(hallazgo=comunicacion.ciclo.hallazgo, usuario=comunicacion.registrado_por, fecha_hora=comunicacion.fecha, accion="COMUNICACION", estado_anterior=comunicacion.ciclo.hallazgo.estado, estado_nuevo=comunicacion.ciclo.hallazgo.estado, comentario=comunicacion.descripcion, metadata_json={"destinatarios": comunicacion.destinatarios, "medio": comunicacion.medio, "origen": "carga_masiva"})
        for datos in self.preparados["pbis"]:
            clave_ciclo = datos.pop("clave_ciclo"); pbi = PBI(ciclo=ciclos[clave_ciclo], **datos); pbi.full_clean(); pbi.save(force_insert=True)
            HistorialHallazgo.objects.create(hallazgo=pbi.ciclo.hallazgo, usuario=pbi.responsable_ti, fecha_hora=pbi.fecha_creacion, accion="REGISTRO_PBI", estado_anterior=pbi.ciclo.hallazgo.estado, estado_nuevo=pbi.ciclo.hallazgo.estado, metadata_json={"pbi": pbi.numero_pbi, "origen": "carga_masiva"})
        for datos in self.preparados["evidencias"]:
            hallazgo = hallazgos[datos["codigo"]]; contexto = datos["contexto"]; ciclo = ciclos.get((datos["codigo"], datos["ciclo"])); referencia = datos["referencia"]
            accion = acciones.get(referencia.casefold()) if contexto == "ACCION" else None
            evaluacion = evaluaciones.get((datos["codigo"], datos["ciclo"], int(referencia))) if contexto == "EVALUACION" else None
            extension = Path(datos["ruta"]).suffix.lower()
            evidencia = Evidencia(hallazgo=hallazgo, accion=accion, analisis=ciclo if contexto == "ANALISIS" else None, evaluacion=evaluacion, cierre=ciclo if contexto == "CIERRE" else None, archivo=f"db/{uuid4().hex}{extension}", nombre_original=Path(datos["ruta"]).name[:255], mime_type=datos["mime"], tamanio=len(datos["contenido"]), subido_por=datos["subido_por"], fecha_carga=datos["fecha_carga"], descripcion=datos["descripcion"])
            evidencia.full_clean(); evidencia.save(force_insert=True)
            ArchivoEvidencia.objects.create(evidencia=evidencia, contenido=datos["contenido"], sha256=hashlib.sha256(datos["contenido"]).hexdigest())
            HistorialHallazgo.objects.create(hallazgo=hallazgo, usuario=evidencia.subido_por, fecha_hora=evidencia.fecha_carga, accion="EVIDENCIA", estado_anterior=hallazgo.estado, estado_nuevo=hallazgo.estado, comentario=evidencia.descripcion, metadata_json={"evidencia": evidencia.pk, "nombre": evidencia.nombre_original, "mime": evidencia.mime_type, "tamanio": evidencia.tamanio, "origen": "carga_masiva"})
        AuditoriaAdministracion.objects.create(usuario=self.ejecutado_por, entidad="Hallazgo", objeto="carga_masiva", accion="importar", antes={}, despues=self.resumen())
        return self.resumen()

    def _actualizar_correlativo(self, hallazgo):
        coincidencia = re.fullmatch(r"SAC-([A-Za-z0-9_]+)-(\d{4})-(\d+)", hallazgo.codigo)
        if not coincidencia:
            return
        tipo_codigo, anio, numero = coincidencia.groups()
        ambito = tipo_codigo if getattr(settings, "SAC_SEQUENCE_SCOPE", "TYPE") == "TYPE" else "GLOBAL"
        contador, _ = CorrelativoSAC.objects.select_for_update().get_or_create(anio=int(anio), ambito=ambito)
        if contador.ultimo_numero < int(numero):
            contador.ultimo_numero = int(numero); contador.save(update_fields=["ultimo_numero"])

    def resumen(self):
        return {"hallazgos": len(self.preparados["hallazgos"]), "ciclos": len(self.preparados["ciclos"]), "compromisos": len(self.preparados["acciones"]), "seguimientos": len(self.preparados["seguimientos"]), "evaluaciones": len(self.preparados["evaluaciones"]), "comunicaciones": len(self.preparados["comunicaciones"]), "pbis": len(self.preparados["pbis"]), "evidencias": len(self.preparados["evidencias"])}


def procesar_carga(archivo, *, ejecutado_por, guardar=False):
    paquete = leer_paquete(archivo)
    importador = ImportadorMasivo(hojas=paquete.hojas, archivos=paquete.archivos, ejecutado_por=ejecutado_por).preparar()
    if not guardar:
        return importador.resumen()
    try:
        return importador.guardar()
    except ErrorCargaMasiva:
        raise
    except ValidationError as exc:
        raise ErrorCargaMasiva(["La base de datos rechazó un valor: " + "; ".join(exc.messages)]) from exc
    except IntegrityError as exc:
        raise ErrorCargaMasiva(["La base de datos rechazó la carga por una relación o valor duplicado. No se guardó ninguna fila."]) from exc
