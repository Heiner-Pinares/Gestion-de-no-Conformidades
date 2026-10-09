"""Generación de las plantillas oficiales de un hallazgo cerrado.

Los libros se editan como paquetes OOXML para conservar exactamente las hojas,
imágenes, estilos, combinaciones de celdas y configuración de impresión de los
archivos entregados por el negocio.
"""
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from django.utils import timezone

from ..registro import RegistroGeneral, nombre_usuario


PLANTILLAS_DIR = Path(__file__).resolve().parent.parent / "plantillas"
SOLICITUD = PLANTILLAS_DIR / "solicitud_accion_correctiva.xlsx"
MATRIZ = PLANTILLAS_DIR / "matriz_control_hallazgos.xlsx"

TIPOS = {
    "solicitud": (SOLICITUD, "Solicitud_accion_correctiva"),
    "matriz": (MATRIZ, "Matriz_control_hallazgo"),
}

FILAS_CAUSA = {
    "1.1": 8, "1.2": 9, "1.3": 10, "1.4": 11, "1.5": 12, "1.6": 13,
    "2.1": 15, "2.2": 16, "2.3": 17, "2.4": 18, "2.5": 19, "2.6": 20,
    "3.1": 22, "3.2": 23, "3.3": 24, "3.4": 25,
    "4.1": 27, "4.2": 35, "4.3": 36, "4.4": 37, "4.5": 38, "4.6": 39,
    "5.1": 41, "5.2": 42, "5.3": 43, "5.4": 44,
    "6.1": 46, "6.2": 47, "6.3": 48, "6.4": 49, "6.5": 50, "6.6": 51,
}


def _limpiar_xml(valor):
    texto = str(valor or "")
    return "".join(
        caracter for caracter in texto
        if caracter in "\t\n\r" or 0x20 <= ord(caracter) <= 0xD7FF or 0xE000 <= ord(caracter) <= 0xFFFD
    )


def _fecha(valor):
    if not valor:
        return ""
    if isinstance(valor, datetime):
        if timezone.is_aware(valor):
            valor = timezone.localtime(valor)
        valor = valor.date()
    return valor.strftime("%d/%m/%Y") if isinstance(valor, date) else valor


class _HojaXML:
    """Edita sólo celdas y filas; el resto del OOXML queda byte por byte intacto.

    Excel es bastante más estricto que LibreOffice con extensiones OOXML. Volver
    a serializar una hoja completa cambia prefijos y contenido de extensiones que
    no necesitamos tocar. Esta clase trabaja sobre el XML original para conservar
    todos esos metadatos del libro oficial.
    """

    def __init__(self, contenido):
        self.texto = contenido.decode("utf-8")

    def bytes(self):
        return self.texto.encode("utf-8")

    def escribir(self, referencia, valor):
        patron = re.compile(
            rf'<c\b(?=[^>]*\br="{re.escape(referencia)}"(?=[\s/>]))(?P<attrs>[^>]*?)'
            rf'(?P<cierre>/>|>(?P<cuerpo>.*?)</c>)',
            re.DOTALL,
        )
        coincidencia = patron.search(self.texto)
        if coincidencia is None:
            raise ValueError(f"La plantilla no contiene la celda {referencia}.")

        atributos = re.sub(r'\s+t="[^"]*"', "", coincidencia.group("attrs"))
        if valor is None or valor == "":
            reemplazo = f"<c{atributos}/>"
        elif isinstance(valor, bool):
            reemplazo = f'<c{atributos} t="b"><v>{1 if valor else 0}</v></c>'
        elif isinstance(valor, (int, float)):
            reemplazo = f'<c{atributos} t="n"><v>{valor}</v></c>'
        else:
            texto = escape(_limpiar_xml(valor))
            reemplazo = (
                f'<c{atributos} t="inlineStr"><is><t xml:space="preserve">'
                f"{texto}</t></is></c>"
            )
        self.texto = self.texto[:coincidencia.start()] + reemplazo + self.texto[coincidencia.end():]

    def insertar_filas_accion(self, cantidad):
        if cantidad <= 0:
            return
        modelo = _buscar_fila(self.texto, 27)
        self.texto = _mover_referencias_hoja(self.texto, 28, cantidad)
        filas = "".join(_renumerar_fila(modelo, 28 + indice) for indice in range(cantidad))
        fila_27 = _buscar_fila(self.texto, 27)
        posicion = self.texto.index(fila_27) + len(fila_27)
        self.texto = self.texto[:posicion] + filas + self.texto[posicion:]

        def agregar_combinadas(match):
            atributos, contenido = match.group(1), match.group(2)
            nuevas = "".join(f'<mergeCell ref="A{fila}:B{fila}"/>' for fila in range(28, 28 + cantidad))
            cuenta = len(re.findall(r"<mergeCell\b", contenido)) + cantidad
            atributos = re.sub(r'\bcount="\d+"', f'count="{cuenta}"', atributos)
            return f"<mergeCells{atributos}>{contenido}{nuevas}</mergeCells>"

        self.texto, total = re.subn(
            r"<mergeCells([^>]*)>(.*?)</mergeCells>", agregar_combinadas, self.texto,
            count=1, flags=re.DOTALL,
        )
        if total != 1:
            raise ValueError("La plantilla no contiene la sección de celdas combinadas.")

    def ampliar_matriz(self, cantidad):
        if cantidad <= 0:
            return
        modelo = _buscar_fila(self.texto, 12)
        filas = "".join(_renumerar_fila(modelo, 13 + indice) for indice in range(cantidad))
        posicion = self.texto.index("</sheetData>")
        self.texto = self.texto[:posicion] + filas + self.texto[posicion:]
        self.texto = re.sub(
            r'(<dimension\b[^>]*\bref=")[^"]+("[^>]*/>)',
            rf'\g<1>A1:AE{12 + cantidad}\2', self.texto, count=1,
        )


def _escribir(hoja, referencia, valor):
    hoja.escribir(referencia, valor)


def _mover_referencia(referencia, desde, cantidad):
    def mover(match):
        columna, fila = match.groups()
        numero = int(fila)
        return f"{columna}{numero + cantidad if numero >= desde else numero}"
    return re.sub(r"(\$?[A-Z]{1,3}\$?)(\d+)", mover, referencia)


def _buscar_fila(texto, numero):
    coincidencia = re.search(rf'<row\b(?=[^>]*\br="{numero}"(?=[\s/>]))[^>]*>.*?</row>', texto, re.DOTALL)
    if coincidencia is None:
        raise ValueError(f"La plantilla no contiene la fila {numero}.")
    return coincidencia.group(0)


def _renumerar_fila(fila, nueva):
    fila = re.sub(r'(<row\b[^>]*\br=")\d+("[^>]*>)', rf'\g<1>{nueva}\2', fila, count=1)
    return re.sub(r'(<c\b[^>]*\br="\$?[A-Z]{1,3}\$?)\d+("[^>]*>)', rf'\g<1>{nueva}\2', fila)


def _mover_referencias_hoja(texto, desde, cantidad):
    def mover_atributo(match):
        return f'{match.group(1)}{_mover_referencia(match.group(2), desde, cantidad)}"'

    texto = re.sub(
        r'((?:\br|\bref|\bsqref|\btopLeftCell)=")([^"]+)"',
        mover_atributo,
        texto,
    )
    texto = re.sub(
        r'(<row\b[^>]*\br=")(\d+)(")',
        lambda match: f'{match.group(1)}{int(match.group(2)) + cantidad if int(match.group(2)) >= desde else match.group(2)}{match.group(3)}',
        texto,
    )
    texto = re.sub(
        r"(<f(?:\s[^>]*)?>)(.*?)(</f>)",
        lambda match: match.group(1) + _mover_referencia(match.group(2), desde, cantidad) + match.group(3),
        texto,
        flags=re.DOTALL,
    )
    return texto


def _limpiar_referencias_formula(nombre, contenido, eliminar_externos=False):
    """Quita relaciones huérfanas después de sustituir las fórmulas por valores.

    Las plantillas originales contienen una cadena de cálculo y, en la solicitud,
    un vínculo a un archivo local del autor. Una vez reemplazadas esas fórmulas,
    conservar dichos objetos hace que Excel intente reparar el libro.
    """
    if nombre == "[Content_Types].xml":
        contenido = re.sub(
            rb'<Override\b[^>]*PartName="/xl/calcChain\.xml"[^>]*/>', b"", contenido,
        )
        if eliminar_externos:
            contenido = re.sub(
                rb'<Override\b[^>]*PartName="/xl/externalLinks/[^\"]+"[^>]*/>', b"", contenido,
            )
    elif nombre == "xl/_rels/workbook.xml.rels":
        contenido = re.sub(
            rb'<Relationship\b(?=[^>]*Type="[^\"]*/calcChain")[^>]*/>', b"", contenido,
        )
        if eliminar_externos:
            contenido = re.sub(
                rb'<Relationship\b(?=[^>]*Type="[^\"]*/externalLink")[^>]*/>', b"", contenido,
            )
    elif nombre == "xl/workbook.xml" and eliminar_externos:
        contenido = re.sub(rb'<externalReferences>.*?</externalReferences>', b"", contenido, flags=re.DOTALL)
    return contenido


def _editar_paquete(ruta, cambios, cambios_libro=None, eliminar_externos=False):
    salida = BytesIO()
    with ZipFile(ruta, "r") as origen, ZipFile(salida, "w", ZIP_DEFLATED) as destino:
        for info in origen.infolist():
            if info.filename == "xl/calcChain.xml":
                continue
            if eliminar_externos and info.filename.startswith("xl/externalLinks/"):
                continue
            contenido = origen.read(info.filename)
            if info.filename in cambios:
                hoja = _HojaXML(contenido)
                cambios[info.filename](hoja)
                contenido = hoja.bytes()
            elif info.filename == "xl/workbook.xml" and cambios_libro:
                contenido = cambios_libro(contenido)
            contenido = _limpiar_referencias_formula(info.filename, contenido, eliminar_externos)
            destino.writestr(info, contenido)
    return salida.getvalue()


def _fila_base(hallazgo):
    filas = list(RegistroGeneral.objects.filter(hallazgo_id=hallazgo.pk))
    return (filas[0] if filas else None), filas


def _generar_solicitud(hallazgo):
    ciclo = hallazgo.ciclo_actual
    acciones = list(ciclo.acciones.select_related("responsable").order_by("pk")) if ciclo else []
    evaluacion = ciclo.evaluaciones.select_related("evaluador").first() if ciclo else None
    fila, _ = _fila_base(hallazgo)
    extras = max(0, len(acciones) - 5)

    def editar_formato(hoja):
        hoja.insertar_filas_accion(extras)
        datos = {
            "C5": hallazgo.tipo_registro.nombre,
            "C6": hallazgo.fuente_deteccion.nombre if hallazgo.fuente_deteccion else "",
            "C7": hallazgo.codigo,
            "C8": hallazgo.ticket_remedy,
            "C9": hallazgo.descripcion,
            "C10": nombre_usuario(hallazgo.responsable),
            "C11": _fecha(hallazgo.fecha_deteccion),
            "C12": _fecha(hallazgo.fecha_registro),
            "C13": _fecha(hallazgo.fecha_solucion),
            "C14": fila.impacto if fila else "",
            "C15": fila.urgencia if fila else "",
            "C16": hallazgo.prioridad_snapshot,
            "C17": {"SI": "Sí - Crítica", "NO": "No - No crítica", "NA": "No aplica"}.get(hallazgo.es_critica, ""),
            "C19": ciclo.causa_raiz if ciclo else "",
            f"C{29 + extras}": _fecha(evaluacion.fecha_evaluacion) if evaluacion else "",
            f"C{30 + extras}": evaluacion.get_resultado_display() if evaluacion else "",
            f"C{31 + extras}": "\n".join(
                parte for parte in [
                    evaluacion.comentario if evaluacion else "",
                    ciclo.comentarios_cierre if ciclo else "",
                ] if parte
            ),
        }
        for referencia, valor in datos.items():
            _escribir(hoja, referencia, valor)
        total_filas = max(5, len(acciones))
        for indice in range(total_filas):
            numero = 23 + indice
            accion = acciones[indice] if indice < len(acciones) else None
            valores = [
                accion.descripcion if accion else "",
                accion.get_tipo_display() if accion else "",
                nombre_usuario(accion.responsable) if accion else "",
                _fecha(accion.fecha_vigente) if accion else "",
                accion.get_estado_display() if accion else "",
                accion.comentario if accion else "",
            ]
            for columna, valor in zip(("A", "C", "D", "E", "F", "G"), valores):
                _escribir(hoja, f"{columna}{numero}", valor)

    def editar_causa(hoja):
        _escribir(hoja, "C4", hallazgo.codigo)
        for fila_causa in FILAS_CAUSA.values():
            for columna in ("J", "K", "L", "M"):
                _escribir(hoja, f"{columna}{fila_causa}", "")
        for respuesta in (ciclo.respuestas if ciclo else []):
            fila_causa = FILAS_CAUSA.get(str(respuesta.get("codigo_snapshot", "")))
            if not fila_causa:
                continue
            columna = {"SI": "J", "NO": "K", "NA": "L"}.get(respuesta.get("respuesta"))
            if columna:
                _escribir(hoja, f"{columna}{fila_causa}", "X")
            _escribir(hoja, f"M{fila_causa}", respuesta.get("comentario", ""))
        control = ciclo.control if ciclo else {}
        for columna, tipo in (("C", "PREVENTIVO"), ("E", "DETECTIVO"), ("G", "CORRECTIVO")):
            _escribir(hoja, f"{columna}28", "X" if tipo in control.get("tipos", []) else "")
        for referencia, valor in {
            "C29": control.get("nombre", ""),
            "C30": control.get("descripcion", ""),
            "C31": {"SI": "Sí", "NO": "No", "NA": "No aplica"}.get(control.get("mitiga_riesgo"), ""),
            "C32": control.get("frecuencia", ""),
            "C33": control.get("responsable", ""),
            "C34": control.get("evidencia", ""),
        }.items():
            _escribir(hoja, referencia, valor)

    def editar_libro(contenido):
        if not extras:
            return contenido
        texto = contenido.decode("utf-8")

        def mover_definido(match):
            contenido_nombre = match.group(2)
            if "Formato" in contenido_nombre:
                contenido_nombre = _mover_referencia(contenido_nombre, 28, extras)
            return match.group(1) + contenido_nombre + match.group(3)

        texto = re.sub(
            r"(<definedName\b[^>]*>)(.*?)(</definedName>)",
            mover_definido,
            texto,
            flags=re.DOTALL,
        )
        return texto.encode("utf-8")

    return _editar_paquete(
        SOLICITUD,
        {"xl/worksheets/sheet1.xml": editar_formato, "xl/worksheets/sheet2.xml": editar_causa},
        editar_libro,
        eliminar_externos=True,
    )


def _generar_matriz(hallazgo):
    _, filas = _fila_base(hallazgo)
    if not filas:
        filas = [None]
    extras = max(0, len(filas) - 7)

    def editar(hoja):
        hoja.ampliar_matriz(extras)
        total_filas = max(7, len(filas))
        for indice in range(total_filas):
            numero_fila = 6 + indice
            fila = filas[indice] if indice < len(filas) else None
            valores = [
                indice + 1 if fila else "",
                fila.gerencia if fila else "", fila.proceso if fila else "", fila.sub_proceso if fila else "",
                fila.fuente_deteccion if fila else "", fila.tipo_hallazgo if fila else "",
                fila.numero_hallazgo if fila else "", fila.ticket_remedy if fila else "",
                fila.descripcion_hallazgo if fila else "", fila.requisito_referencia if fila else "",
                fila.responsable_proceso if fila else "", _fecha(fila.fecha_deteccion) if fila else "",
                _fecha(fila.fecha_registro) if fila else "", fila.impacto if fila else "",
                fila.urgencia if fila else "", fila.prioridad_criticidad if fila else "",
                fila.no_conformidad_critica if fila else "", fila.causas_raiz if fila else "",
                fila.tipo_accion if fila else "", fila.descripcion_accion if fila else "",
                fila.responsable if fila else "", _fecha(fila.fet) if fila else "", fila.estado if fila else "",
                fila.evidencia_implementacion if fila else "", fila.porcentaje_avance if fila else "",
                fila.comentario if fila else "", _fecha(fila.fecha_evaluacion_eficacia) if fila else "",
                fila.resultado_eficacia if fila else "", _fecha(fila.fecha_cierre) if fila else "",
                fila.auditor_verificador if fila else "", fila.comentarios if fila else "",
            ]
            for columna, valor in zip(
                ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", "AA", "AB", "AC", "AD", "AE"),
                valores,
            ):
                _escribir(hoja, f"{columna}{numero_fila}", valor)

    return _editar_paquete(MATRIZ, {"xl/worksheets/sheet1.xml": editar})


def generar_plantilla(hallazgo, tipo):
    """Devuelve ``(contenido, nombre)`` para una plantilla oficial ya completada."""
    if tipo not in TIPOS:
        raise ValueError("Tipo de plantilla no válido.")
    contenido = _generar_solicitud(hallazgo) if tipo == "solicitud" else _generar_matriz(hallazgo)
    return contenido, f"{hallazgo.codigo}_{TIPOS[tipo][1]}.xlsx"
