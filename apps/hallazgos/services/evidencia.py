import io
import warnings
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from PIL import Image, UnidentifiedImageError

from apps.accounts.permissions import puede_gestionar, puede_validar
from apps.hallazgos.models import Evidencia
from .common import bloquear, ciclo_vigente, exigir, registrar

MAX_ARCHIVO = 10 * 1024 * 1024


def validar_archivo(archivo):
    exigir(archivo is not None and 0 < archivo.size <= MAX_ARCHIVO, "La evidencia debe pesar entre 1 byte y 10 MB.")
    extension = Path(archivo.name).suffix.lower()
    exigir(extension in {".pdf", ".png", ".jpg", ".jpeg"}, "Se admiten evidencias PDF, PNG y JPEG.")
    archivo.seek(0)
    contenido = archivo.read(MAX_ARCHIVO + 1)
    archivo.seek(0)
    exigir(len(contenido) <= MAX_ARCHIVO, "El archivo supera 10 MB.")
    if extension == ".pdf":
        exigir(contenido.startswith(b"%PDF-") and b"%%EOF" in contenido[-2048:], "El contenido no corresponde a un PDF válido.")
        return "application/pdf"
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
            exigir(ciclo_contexto.pk == vigente.pk, "Los ciclos anteriores son históricos.")
            if analisis is not None:
                exigir(analisis.analisis_inicio is not None, "Inicie el análisis antes de adjuntar evidencia a él.")
        mime = validar_archivo(archivo)
        evidencia = Evidencia(hallazgo=hallazgo, accion=accion, analisis=analisis, evaluacion=evaluacion,
            cierre=cierre, archivo=archivo, nombre_original=Path(archivo.name).name[:255], mime_type=mime,
            tamanio=archivo.size, subido_por=usuario, descripcion=descripcion)
        evidencia.full_clean()
        try:
            evidencia.save()
            registrar(hallazgo, usuario, "EVIDENCIA", descripcion, metadata={"evidencia": evidencia.pk, "nombre": evidencia.nombre_original, "mime": mime, "tamanio": evidencia.tamanio})
        except Exception:
            if evidencia.archivo and evidencia.archivo._committed:
                evidencia.archivo.delete(save=False)
            raise
        return evidencia
