from .permissions import es_administrador, es_validador, tiene_permiso


def perfil(request):
    usuario = request.user
    if not usuario.is_authenticated:
        return {}
    from apps.hallazgos.selectors import hallazgos_visibles
    return {
        "es_admin": es_administrador(usuario),
        "es_calidad": es_validador(usuario),
        "puede_registrar": tiene_permiso(usuario, "registrar_hallazgo"),
        "roles_usuario": list(usuario.groups.values_list("name", flat=True)),
        "notificaciones_no_leidas": usuario.notificaciones.filter(leida=False, hallazgo__in=hallazgos_visibles(usuario)).count(),
    }
