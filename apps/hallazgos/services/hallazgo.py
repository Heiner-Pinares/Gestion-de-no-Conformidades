import logging
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts.permissions import puede_validar
from apps.catalogos.models import MatrizPrioridad
from apps.hallazgos.models import CorrelativoSAC, Hallazgo
from .common import bloquear, campos_permitidos, exigir, notificar, registrar

CAMPOS_HALLAZGO = ["titulo", "tipo_registro", "fuente_deteccion", "proceso", "subproceso", "actividad", "descripcion", "ticket_remedy", "responsable", "fecha_deteccion", "fecha_solucion", "impacto_clientes", "impacto_tiempo", "impacto_soles", "urgencia", "es_critica", "origen_tecnologico", "criterio_categoria", "requisito_referencia", "aplica_impacto", "justificacion_no_impacto"]


class CodigoSACService:
    @staticmethod
    def previsualizar(*, tipo):
        """Muestra el próximo código probable sin reservar ni alterar el correlativo."""
        anio = timezone.localdate().year
        modo = getattr(settings, "SAC_SEQUENCE_SCOPE", "TYPE")
        exigir(modo in {"TYPE", "YEAR"}, "SAC_SEQUENCE_SCOPE debe ser TYPE o YEAR.")
        ambito = tipo.codigo if modo == "TYPE" else "GLOBAL"
        ultimo = CorrelativoSAC.objects.filter(anio=anio, ambito=ambito).values_list("ultimo_numero", flat=True).first() or 0
        return f"SAC-{tipo.codigo}-{anio}-{ultimo + 1:04d}"

    @staticmethod
    @transaction.atomic
    def generar(*, tipo):
        anio = timezone.localdate().year
        modo = getattr(settings, "SAC_SEQUENCE_SCOPE", "TYPE")
        exigir(modo in {"TYPE", "YEAR"}, "SAC_SEQUENCE_SCOPE debe ser TYPE o YEAR.")
        ambito = tipo.codigo if modo == "TYPE" else "GLOBAL"
        # UniqueConstraint + get_or_create resuelven también la primera reserva simultánea.
        CorrelativoSAC.objects.get_or_create(anio=anio, ambito=ambito)
        contador = CorrelativoSAC.objects.select_for_update().get(anio=anio, ambito=ambito)
        otros = CorrelativoSAC.objects.filter(anio=anio).exclude(ambito=ambito)
        if (modo == "YEAR" and otros.exists()) or (modo == "TYPE" and otros.filter(ambito="GLOBAL").exists()):
            raise ValidationError("El modo de correlativo SAC cambió después de reservar códigos. Requiere migración controlada; restaure SAC_SEQUENCE_SCOPE.")
        contador.ultimo_numero += 1
        contador.save(update_fields=["ultimo_numero"])
        return f"SAC-{tipo.codigo}-{anio}-{contador.ultimo_numero:04d}"


class ImpactoService:
    @staticmethod
    def calcular(*, clientes, tiempo, soles):
        valores = [clientes, tiempo, soles]
        exigir(all(valor in (1, 2, 3) and not isinstance(valor, bool) for valor in valores), "Seleccione un nivel válido (1 a 3) para clientes, tiempo y soles.")
        return max(valores)

    @staticmethod
    def selecciones(*, clientes, tiempo, soles):
        """Captura los rangos visibles al evaluar; no dependen de cambios futuros."""
        from apps.catalogos.models import ConfiguracionImpacto

        configuracion = ConfiguracionImpacto.objects.first() or ConfiguracionImpacto()
        rangos = configuracion.rangos_usuario
        claves = {1: "bajo", 2: "medio", 3: "alto"}
        return {
            "impacto_clientes_seleccion": rangos["clientes"][claves[clientes]],
            "impacto_tiempo_seleccion": rangos["tiempo"][claves[tiempo]],
            "impacto_financiero_seleccion": rangos["financiero"][claves[soles]],
        }


class UrgenciaService:
    @staticmethod
    def seleccion(*, area, urgencia):
        from apps.catalogos.models import ConfiguracionUrgencia
        codigo = ConfiguracionUrgencia.codigo_para_area(area)
        configuracion = ConfiguracionUrgencia.objects.filter(codigo=codigo, activo=True).first() if codigo else None
        if configuracion:
            return configuracion.seleccion_para(urgencia.valor), configuracion.get_codigo_display()
        return urgencia.nombre, area or ""


class PrioridadService:
    @staticmethod
    def calcular(*, impacto, urgencia):
        matriz = MatrizPrioridad.objects.select_related("prioridad").filter(impacto__valor=impacto, urgencia=urgencia, activo=True, prioridad__activo=True).first()
        if matriz is None:
            logging.getLogger(__name__).warning("Matriz de prioridad no configurada: impacto=%s, urgencia=%s", impacto, urgencia.pk)
        exigir(matriz is not None, "No existe una matriz activa para el impacto y urgencia seleccionados. Solicite su configuración.")
        return matriz.prioridad


def validar_datos(hallazgo, *, completo=False, fecha_cambiada=True, actualizar_snapshot_impacto=False, actualizar_snapshot_urgencia=False):
    if fecha_cambiada and hallazgo.fecha_solucion:
        exigir(hallazgo.fecha_solucion >= timezone.localdate(), "La fecha de solución no puede ser anterior a la fecha actual.")
    if hallazgo.fecha_deteccion:
        exigir(hallazgo.fecha_deteccion <= timezone.now(), "La fecha de detección no puede estar en el futuro.")
    if hallazgo.subproceso_id:
        exigir(hallazgo.subproceso.proceso_id == hallazgo.proceso_id, "El subproceso no pertenece al proceso seleccionado.")
    exigir(hallazgo.responsable.is_active, "El responsable debe ser un usuario activo.")
    for nombre in ("tipo_registro", "fuente_deteccion", "proceso", "subproceso", "urgencia"):
        obj = getattr(hallazgo, nombre)
        if obj is not None:
            exigir(obj.activo, f"El catálogo {nombre.replace('_', ' ')} está inactivo.")
    if not hallazgo.aplica_impacto:
        exigir(not hallazgo.origen_tecnologico, "El impacto es obligatorio para un origen tecnológico.")
        exigir(bool(hallazgo.justificacion_no_impacto.strip()), "Justifique por qué no aplica el impacto.")
        hallazgo.impacto_clientes = hallazgo.impacto_tiempo = hallazgo.impacto_soles = None
        hallazgo.impacto_clientes_seleccion = ""
        hallazgo.impacto_tiempo_seleccion = ""
        hallazgo.impacto_financiero_seleccion = ""
        hallazgo.impacto_resultante = hallazgo.urgencia = hallazgo.prioridad = None
        hallazgo.urgencia_seleccion = hallazgo.urgencia_area = ""
        hallazgo.prioridad_snapshot = "No aplica: " + hallazgo.justificacion_no_impacto[:150]
    else:
        valores = [hallazgo.impacto_clientes, hallazgo.impacto_tiempo, hallazgo.impacto_soles]
        exigir(all(v is None or (v in (1, 2, 3) and not isinstance(v, bool)) for v in valores), "Los niveles de impacto deben ser 1, 2 o 3.")
        if actualizar_snapshot_impacto and None not in valores:
            for campo, seleccion in ImpactoService.selecciones(
                clientes=valores[0], tiempo=valores[1], soles=valores[2]
            ).items():
                setattr(hallazgo, campo, seleccion)
        hallazgo.impacto_resultante = ImpactoService.calcular(clientes=valores[0], tiempo=valores[1], soles=valores[2]) if None not in valores else None
        hallazgo.prioridad = None
        hallazgo.prioridad_snapshot = ""
        if hallazgo.impacto_resultante and hallazgo.urgencia_id:
            if actualizar_snapshot_urgencia:
                hallazgo.urgencia_seleccion, hallazgo.urgencia_area = UrgenciaService.seleccion(
                    area=hallazgo.registrado_por.area, urgencia=hallazgo.urgencia
                )
            hallazgo.prioridad = PrioridadService.calcular(impacto=hallazgo.impacto_resultante, urgencia=hallazgo.urgencia)
            hallazgo.prioridad_snapshot = hallazgo.prioridad.nombre
    # La matriz prevalece sobre cualquier valor enviado por el navegador.
    # Una prioridad crítica siempre requiere el recorrido de causa raíz.
    if hallazgo.prioridad_id and hallazgo.prioridad.codigo == "CRITICA":
        hallazgo.es_critica = "SI"
    if completo:
        obligatorios = ["titulo", "descripcion", "fuente_deteccion", "fecha_deteccion", "fecha_solucion"]
        faltantes = [nombre.replace('_', ' ') for nombre in obligatorios if not getattr(hallazgo, nombre)]
        exigir(not faltantes, "Complete: " + ", ".join(faltantes) + ".")
        exigir(hallazgo.es_critica in ("SI", "NO"), "Defina la criticidad como Sí o No antes de enviar. No aplica requiere revisión.")
        if hallazgo.aplica_impacto:
            exigir(hallazgo.impacto_resultante is not None and hallazgo.urgencia_id is not None and hallazgo.prioridad_id is not None, "Complete la matriz de impacto y la urgencia.")
    hallazgo.full_clean()


class HallazgoService:
    @staticmethod
    @transaction.atomic
    def crear(*, usuario, datos, borrador=True):
        if not usuario.is_authenticated or not usuario.has_perm("accounts.registrar_hallazgo"):
            raise PermissionDenied("No tiene permiso para registrar hallazgos.")
        campos_permitidos(datos, CAMPOS_HALLAZGO)
        exigir(all(datos.get(n) for n in ["titulo", "tipo_registro", "proceso", "responsable"]), "Complete título, tipo, proceso y responsable.")
        hallazgo = Hallazgo(**datos, registrado_por=usuario, updated_by=usuario, estado="BORRADOR")
        hallazgo.codigo = CodigoSACService.generar(tipo=hallazgo.tipo_registro)
        validar_datos(hallazgo, completo=not borrador, actualizar_snapshot_impacto=True, actualizar_snapshot_urgencia=True)
        hallazgo.save()
        registrar(hallazgo, usuario, "CREACION", "Hallazgo creado como borrador.", anterior="")
        if not borrador:
            from .workflow import WorkflowService
            return WorkflowService.continuar_identificacion(usuario=usuario, hallazgo=hallazgo)
        return hallazgo

    @staticmethod
    @transaction.atomic
    def actualizar(*, usuario, hallazgo, datos, version=None, completo=False):
        hallazgo = bloquear(hallazgo, version)
        campos_permitidos(datos, CAMPOS_HALLAZGO)
        es_autor = usuario.pk in {hallazgo.registrado_por_id, hallazgo.responsable_id} and usuario.has_perm("accounts.registrar_hallazgo")
        es_revisor = hallazgo.estado == "PENDIENTE_VALIDACION" and puede_validar(usuario, hallazgo)
        ciclo = hallazgo.ciclo_actual
        accion_sin_actividades = hallazgo.estado == "ACCION_INMEDIATA" and ciclo is not None and not ciclo.acciones.exists()
        if not (es_autor and (hallazgo.estado in {"BORRADOR", "DEVUELTO", "EN_ANALISIS"} or accion_sin_actividades)) and not es_revisor:
            raise PermissionDenied("La identificación solo se puede corregir antes de registrar actividades o tras una devolución.")
        tipo_nuevo = datos.get("tipo_registro", hallazgo.tipo_registro)
        cambio_tipo = tipo_nuevo.pk != hallazgo.tipo_registro_id
        if cambio_tipo:
            exigir(
                es_autor and (hallazgo.estado == "EN_ANALISIS" or accion_sin_actividades),
                "El tipo solo puede corregirse antes de registrar actividades.",
            )
        if es_revisor:
            # No puede reasignar proceso para atribuirse autoridad sobre otro caso.
            exigir(datos.get("proceso", hallazgo.proceso).pk == hallazgo.proceso_id, "El proceso solo puede corregirse tras devolver el registro.")
        estado_anterior = hallazgo.estado
        datos_anteriores = {k: str(getattr(hallazgo, k)) for k in datos}
        codigo_anterior = hallazgo.codigo
        impacto_cambiado = any(
            campo in datos and datos[campo] != getattr(hallazgo, campo)
            for campo in ("impacto_clientes", "impacto_tiempo", "impacto_soles", "aplica_impacto")
        )
        urgencia_cambiada = "urgencia" in datos and datos["urgencia"] != hallazgo.urgencia
        if cambio_tipo:
            hallazgo.codigo = CodigoSACService.generar(tipo=tipo_nuevo)
        fecha_cambiada = datos.get("fecha_solucion", hallazgo.fecha_solucion) != hallazgo.fecha_solucion
        for campo, valor in datos.items():
            setattr(hallazgo, campo, valor)
        if hallazgo.estado in {"EN_ANALISIS", "ACCION_INMEDIATA"} and ciclo is not None and not ciclo.acciones.exists():
            hallazgo.estado = "EN_ANALISIS" if hallazgo.es_critica == "SI" else "ACCION_INMEDIATA"
        validar_datos(
            hallazgo,
            completo=completo,
            fecha_cambiada=fecha_cambiada,
            actualizar_snapshot_impacto=impacto_cambiado,
            actualizar_snapshot_urgencia=urgencia_cambiada,
        )
        hallazgo.save()
        metadata = {"antes": datos_anteriores, "despues": {k: str(getattr(hallazgo, k)) for k in datos}}
        if cambio_tipo:
            metadata["codigo_anterior"] = codigo_anterior
            metadata["codigo_nuevo"] = hallazgo.codigo
        registrar(hallazgo, usuario, "ACTUALIZACION", anterior=estado_anterior, metadata=metadata)
        return hallazgo
