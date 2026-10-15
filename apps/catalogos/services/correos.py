"""Configuración DML de destinatarios adicionales de compromisos."""

from hashlib import sha256

from django.db.models import Q

from apps.catalogos.models import Catalogo


CLASE_COMPATIBLE = "CATEGORIA"
TIPO_PARA = "PARA"
TIPO_COPIA = "CC"
TIPOS_CORREO = (
    (TIPO_PARA, "Destinatario (Para)"),
    (TIPO_COPIA, "Copia (CC)"),
)
PREFIJOS_CORREO = {
    TIPO_PARA: "CFG_MAIL_TO_",
    TIPO_COPIA: "CFG_MAIL_CC_",
}


def _tipo_valido(tipo):
    tipo = str(tipo or "").strip().upper()
    if tipo not in PREFIJOS_CORREO:
        raise ValueError("Tipo de destinatario de correo no válido.")
    return tipo


def correos_queryset(tipo=None):
    """Obtiene únicamente los registros técnicos de correo del catálogo."""
    consulta = Catalogo.objects.filter(clase=CLASE_COMPATIBLE)
    if tipo:
        return consulta.filter(codigo__startswith=PREFIJOS_CORREO[_tipo_valido(tipo)])
    return consulta.filter(
        Q(codigo__startswith=PREFIJOS_CORREO[TIPO_PARA])
        | Q(codigo__startswith=PREFIJOS_CORREO[TIPO_COPIA])
    )


def tipo_correo(registro):
    for tipo, prefijo in PREFIJOS_CORREO.items():
        if registro.codigo.startswith(prefijo):
            return tipo
    return None


def guardar_correo(*, tipo, correo):
    """Crea o reactiva una dirección sin requerir nuevas tablas o columnas."""
    tipo = _tipo_valido(tipo)
    correo = str(correo).strip()
    existente = correos_queryset(tipo).filter(nombre__iexact=correo).first()
    if existente:
        if not existente.activo:
            existente.activo = True
            existente.save(update_fields=["activo"])
        return existente, False

    huella = sha256(correo.casefold().encode("utf-8")).hexdigest()[:18].upper()
    registro, creado = Catalogo.objects.get_or_create(
        clase=CLASE_COMPATIBLE,
        codigo=f"{PREFIJOS_CORREO[tipo]}{huella}",
        defaults={"nombre": correo, "activo": True},
    )
    if not creado:
        if registro.nombre.casefold() != correo.casefold():
            raise ValueError("No se pudo generar un identificador único para el correo.")
        if not registro.activo:
            registro.activo = True
            registro.save(update_fields=["activo"])
    return registro, creado


def destinatarios_adicionales():
    """Devuelve listas activas para To y CC conservando el orden del catálogo."""
    return {
        tipo: list(
            correos_queryset(tipo)
            .filter(activo=True)
            .order_by("orden", "pk")
            .values_list("nombre", flat=True)
        )
        for tipo in (TIPO_PARA, TIPO_COPIA)
    }
