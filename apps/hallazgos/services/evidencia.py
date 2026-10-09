import hashlib
import io
import warnings
import zipfile
from pathlib import Path
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from PIL import Image, UnidentifiedImageError

from apps.accounts.permissions import puede_gestionar, puede_validar
from apps.hallazgos.models import ArchivoEvidencia, Evidencia
from .common import bloquear, ciclo_vigente, exigir, registrar

MAX_ARCHIVO = 10 * 1024 * 1024


def validar_archivo(archivo):
    exigir(archivo is not None and 0 < archivo.size <= MAX_ARCHIVO, "La evidencia debe pesar entre 1 byte y 10 MB.")
    extension = Path(archivo.name).suffix.lower()
    exigir(extension in {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"},
           "Se admiten evidencias PDF, DOC, DOCX, XLS, XLSX, PNG y JPEG.")
    archivo.seek(0)
    contenido = archivo.read(MAX_ARCHIVO + 1)
    archivo.seek(0)
    exigir(len(contenido) <= MAX_ARCHIVO, "El archivo supera 10 MB.")
    if extension == ".pdf":
        exigir(contenido.startswith(b"%PDF-") and b"%%EOF" in contenido[-2048:], "El contenido no corresponde a un PDF válido.")
        return "application/pdf"
    if extension in {".doc", ".xls"}:
        exigir(contenido.startswith(bytes.fromhex("D0CF11E0A1B11AE1")), "El contenido no corresponde a un documento de Office válido.")
        return "application/msword" if extension == ".doc" else "application/vnd.ms-excel"
    if extension in {".docx", ".xlsx"}:
        try:
            with zipfile.ZipFile(io.BytesIO(contenido)) as paquete:
                nombres = set(paquete.namelist())
                exigir(paquete.testzip() is None, "El documento de Office está dañado o no es válido.")
        except (zipfile.BadZipFile, OSError) as exc:
            raise ValidationError("El documento de Office está dañado o no es válido.") from exc
        requerido = "word/document.xml" if extension == ".docx" else "xl/workbook.xml"
        exigir("[Content_Types].xml" in nombres and requerido in nombres, "El contenido no coincide con la extensión del documento.")
        return ("application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if extension == ".docx" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(contenido)) as imagen:
                formato = imagen.format
                imagen.verify()
        exigir(formato in {"PNG", "JPEG"}, "El formato de imagen no está permitido.")
        exigir((formato == "PNG" and extension == ".png") or (formato == "JPEG" and extension in {".jpg", ".jpeg"}), "La extensión no coincide con el contenido de imagen.")
        return "image/png" if formato == "PNG" else "image/jpeg"
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError("El contenido de imagen está dañado o no es seguro.") from exc


class EvidenciaService:
    @staticmethod
    @transaction.atomic
    def subir(*, usuario, hallazgo, archivo, descripcion="", accion=None, analisis=None, evaluacion=None, cierre=None):
        hallazgo = bloquear(hallazgo)
        exigir(hallazgo.estado not in {"CERRADO", "CANCELADO"}, "El hallazgo cerrado o cancelado no admite nuevas evidencias.")
        contextos = [c for c in (accion, analisis, evaluacion, cierre) if c is not None]
        exigir(len(contextos) <= 1, "Asocie la evidencia a un único contexto.")
        autor_borrador = hallazgo.estado in {"BORRADOR", "DEVUELTO"} and hallazgo.registrado_por_id == usuario.pk and usuario.has_perm("accounts.registrar_hallazgo")
        ejecutor = accion is not None and accion.responsable_id == usuario.pk and usuario.has_perm("accounts.registrar_hallazgo")
        if not (autor_borrador or puede_gestionar(usuario, hallazgo) or puede_validar(usuario, hallazgo) or ejecutor):
            raise PermissionDenied("No tiene permiso para adjuntar evidencias a este caso.")
        if contextos:
            contexto = contextos[0]
            ciclo_contexto = contexto if contexto is analisis or contexto is cierre else contexto.ciclo
            exigir(ciclo_contexto.hallazgo_id == hallazgo.pk, "La evidencia no puede relacionarse con otro hallazgo.")
            vigente = ciclo_vigente(hallazgo)
            exigir(ciclo_contexto.pk == vigente.pk, "Los planes anteriores son históricos.")
            if analisis is not None:
                exigir(analisis.analisis_inicio is not None, "Inicie el análisis antes de adjuntar evidencia a él.")
        mime = validar_archivo(archivo)
        archivo.seek(0)
        contenido = archivo.read()
        archivo.seek(0)
        extension = Path(archivo.name).suffix.lower()
        evidencia = Evidencia(hallazgo=hallazgo, accion=accion, analisis=analisis, evaluacion=evaluacion,
            cierre=cierre, archivo=f"db/{uuid4().hex}{extension}", nombre_original=Path(archivo.name).name[:255], mime_type=mime,
            tamanio=archivo.size, subido_por=usuario, descripcion=descripcion)
        evidencia.full_clean()
        evidencia.save()
        ArchivoEvidencia.objects.create(
            evidencia=evidencia,
            contenido=contenido,
            sha256=hashlib.sha256(contenido).hexdigest(),
        )
        registrar(hallazgo, usuario, "EVIDENCIA", descripcion, metadata={"evidencia": evidencia.pk, "nombre": evidencia.nombre_original, "mime": mime, "tamanio": evidencia.tamanio})
        return evidencia
