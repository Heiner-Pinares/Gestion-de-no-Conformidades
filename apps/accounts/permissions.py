"""Autorización funcional: permisos más relación con cada caso."""
from django.core.exceptions import PermissionDenied


def tiene_permiso(usuario, permiso):
    return bool(usuario.is_authenticated and usuario.is_active and usuario.has_perm(f"accounts.{permiso}"))


def es_administrador(usuario):
    return tiene_permiso(usuario, "administrar_plataforma")


def es_validador(usuario):
    return tiene_permiso(usuario, "validar_hallazgo")


def asignado_al_proceso(usuario, hallazgo):
    return hallazgo.proceso.validadores.filter(pk=usuario.pk, is_active=True).exists()


def puede_validar(usuario, hallazgo):
    return (es_validador(usuario) and hallazgo.registrado_por_id != usuario.pk
            and asignado_al_proceso(usuario, hallazgo))


def puede_gestionar(usuario, hallazgo):
    if not usuario.is_authenticated or not usuario.is_active:
        return False
    responsable = hallazgo.responsable_id == usuario.pk and tiene_permiso(usuario, "registrar_hallazgo")
    calidad = tiene_permiso(usuario, "gestionar_tratamiento") and asignado_al_proceso(usuario, hallazgo)
    return responsable or calidad


def puede_ver(usuario, hallazgo):
    if not usuario.is_authenticated or not usuario.is_active:
        return False
    if tiene_permiso(usuario, "ver_todos_hallazgos"):
        return True
    if usuario.pk in (hallazgo.registrado_por_id, hallazgo.responsable_id):
        return True
    if es_validador(usuario) and asignado_al_proceso(usuario, hallazgo):
        return True
    return hallazgo.ciclos.filter(acciones__responsable=usuario).exists()


def exigir_administrador(usuario):
    if not es_administrador(usuario):
        raise PermissionDenied("No tienes permiso para administrar la plataforma.")
