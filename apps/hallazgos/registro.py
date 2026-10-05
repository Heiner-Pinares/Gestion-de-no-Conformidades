"""Proyección del registro general calculada por el backend, sin vista SQL."""
from datetime import date, datetime
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.utils import timezone

COLUMNAS_REGISTRO = [('numero', 'N°'), ('gerencia', 'Gerencia'), ('proceso', 'Proceso'), ('sub_proceso', 'Sub Proceso'), ('fuente_deteccion', 'Fuente de detección'), ('tipo_hallazgo', 'Tipo de Hallazgo'), ('numero_hallazgo', 'N° Hallazgo'), ('ticket_remedy', 'N° Ticket Remedy'), ('descripcion_hallazgo', 'Descripción del Hallazgo'), ('requisito_referencia', 'Requisito de referencia'), ('responsable_proceso', 'Responsable del proceso'), ('fecha_deteccion', 'Fecha de detección'), ('fecha_registro', 'Fecha de registro'), ('impacto', 'Impacto'), ('impacto_clientes_seleccion', 'Clientes afectados · Rango seleccionado'), ('impacto_tiempo_seleccion', 'Tiempo de afectación · Rango seleccionado'), ('impacto_financiero_seleccion', 'Impacto financiero · Rango seleccionado'), ('urgencia', 'Urgencia'), ('prioridad_criticidad', 'Prioridad / Criticidad'), ('no_conformidad_critica', '¿No conformidad crítica?'), ('causas_raiz', 'Causa(s) raíz identificada(s)'), ('tipo_accion', 'Tipo de Acción'), ('descripcion_accion', 'Descripción de la Acción'), ('responsable', 'Responsable'), ('fet', 'FET'), ('estado', 'Estado'), ('evidencia_implementacion', 'Evidencia de implementación'), ('porcentaje_avance', 'Porcentaje de Avance'), ('comentario', 'Comentario'), ('fecha_evaluacion_eficacia', 'Fecha de evaluación de eficacia'), ('resultado_eficacia', 'Resultado de eficacia'), ('fecha_cierre', 'Fecha de cierre'), ('auditor_verificador', 'Auditor o Verificador'), ('comentarios', 'Comentarios')]


def nombre_usuario(usuario):
    if not usuario:
        return ""
    return usuario.get_full_name().strip() or usuario.username


class RegistroCollection(list):
    def count(self):
        return len(self)

    def iterator(self, chunk_size=500):
        return iter(self)

    def filter(self, **kwargs):
        def coincide(fila):
            for clave, valor in kwargs.items():
                if clave.endswith("__in"):
                    campo = clave[:-4]
                    if getattr(fila, campo) not in set(valor):
                        return False
                elif getattr(fila, clave) != valor:
                    return False
            return True
        return RegistroCollection(item for item in self if coincide(item))

    def get(self, **kwargs):
        encontrados = self.filter(**kwargs)
        if not encontrados:
            raise ObjectDoesNotExist("No existe la fila solicitada del registro general.")
        if len(encontrados) > 1:
            raise MultipleObjectsReturned("La consulta devolvió más de una fila.")
        return encontrados[0]


class RegistroGeneralManager:
    def all(self):
        return self._construir({})

    def filter(self, **kwargs):
        return self._construir(kwargs)

    def get(self, **kwargs):
        return self._construir(kwargs).get()

    def _construir(self, filtros):
        from apps.catalogos.models import Impacto
        from .models import Hallazgo

        hallazgos = Hallazgo.objects.select_related(
            "proceso__responsable", "subproceso", "fuente_deteccion", "tipo_registro", "urgencia"
        ).order_by("pk")
        hallazgo_id = filtros.pop("hallazgo_id", None)
        hallazgo_ids = filtros.pop("hallazgo_id__in", None)
        if hallazgo_id is not None:
            hallazgos = hallazgos.filter(pk=hallazgo_id)
        if hallazgo_ids is not None:
            if hasattr(hallazgo_ids, "values_list"):
                hallazgo_ids = hallazgo_ids.values_list("pk", flat=True)
            else:
                hallazgo_ids = [v.get("pk") if isinstance(v, dict) else v for v in hallazgo_ids]
            hallazgos = hallazgos.filter(pk__in=hallazgo_ids)

        impactos = dict(Impacto.objects.values_list("valor", "nombre"))
        filas = []
        for h in hallazgos:
            ciclos = list(h.ciclos.order_by("numero", "pk"))
            unidades = [(None, None)] if not ciclos else []
            for ciclo in ciclos:
                acciones = list(ciclo.acciones.order_by("pk"))
                unidades.extend((ciclo, accion) for accion in acciones or [None])
            for ciclo, accion in unidades:
                evaluacion = ciclo.evaluaciones.order_by("-fecha_registro", "-pk").first() if ciclo else None
                validacion = h.historial.filter(accion="VALIDAR").order_by("-fecha_hora", "-pk").first()
                verificador = (evaluacion.evaluador if evaluacion else None) or (ciclo.responsable_cierre if ciclo else None) or (validacion.usuario if validacion else None)
                evidencias = h.evidencias.filter(accion=accion) if accion else h.evidencias.filter(accion__isnull=True, analisis__isnull=True, evaluacion__isnull=True, cierre__isnull=True)
                fila = RegistroGeneral(
                    fila_id=f"{h.pk}:{ciclo.pk if ciclo else 0}:{accion.pk if accion else 0}",
                    hallazgo_id=h.pk, ciclo_id=ciclo.pk if ciclo else None, accion_id=accion.pk if accion else None,
                    gerencia=h.proceso.gerencia, proceso=h.proceso.nombre,
                    sub_proceso=h.subproceso.nombre if h.subproceso else "",
                    fuente_deteccion=h.fuente_deteccion.nombre if h.fuente_deteccion else "",
                    tipo_hallazgo=h.tipo_registro.nombre, numero_hallazgo=h.codigo,
                    ticket_remedy=h.ticket_remedy, descripcion_hallazgo=h.descripcion,
                    requisito_referencia=h.requisito_referencia,
                    responsable_proceso=nombre_usuario(h.proceso.responsable),
                    fecha_deteccion=h.fecha_deteccion, fecha_registro=h.fecha_registro,
                    impacto="No aplica" if not h.aplica_impacto else impactos.get(h.impacto_resultante, ""),
                    impacto_clientes_seleccion="No aplica" if not h.aplica_impacto else h.impacto_clientes_seleccion,
                    impacto_tiempo_seleccion="No aplica" if not h.aplica_impacto else h.impacto_tiempo_seleccion,
                    impacto_financiero_seleccion="No aplica" if not h.aplica_impacto else h.impacto_financiero_seleccion,
                    urgencia="No aplica" if not h.aplica_impacto else (h.urgencia_seleccion or (h.urgencia.nombre if h.urgencia else "")),
                    prioridad_criticidad=h.prioridad_snapshot,
                    no_conformidad_critica={"SI": "Sí", "NO": "No", "NA": "No aplica"}.get(h.es_critica, ""),
                    causas_raiz=ciclo.causa_raiz if ciclo else "",
                    tipo_accion={"INMEDIATA": "Solución inmediata", "ACCION_INMEDIATA": "Acción inmediata", "CORRECTIVA": "Acción correctiva"}.get(accion.tipo, "") if accion else "",
                    descripcion_accion=accion.descripcion if accion else "",
                    responsable=nombre_usuario(accion.responsable) if accion else "",
                    fet=accion.fecha_vigente if accion else None,
                    estado=accion.get_estado_display() if accion else h.get_estado_display(),
                    evidencia_implementacion="\n".join(evidencias.order_by("pk").values_list("nombre_original", flat=True)),
                    porcentaje_avance=accion.porcentaje_avance if accion else None,
                    comentario=accion.comentario if accion else "",
                    fecha_evaluacion_eficacia=evaluacion.fecha_evaluacion if evaluacion else None,
                    resultado_eficacia=evaluacion.get_resultado_display() if evaluacion else "",
                    fecha_cierre=ciclo.fecha_cierre if ciclo else None,
                    auditor_verificador=nombre_usuario(verificador),
                    comentarios="\n".join(x for x in [f"Evaluación: {evaluacion.comentario}" if evaluacion and evaluacion.comentario else "", f"Cierre: {ciclo.comentarios_cierre}" if ciclo and ciclo.comentarios_cierre else ""] if x),
                )
                filas.append(fila)
        for numero, fila in enumerate(filas, 1):
            fila.numero = numero
        coleccion = RegistroCollection(filas)
        return coleccion.filter(**filtros) if filtros else coleccion


class RegistroGeneral:
    objects = RegistroGeneralManager()

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def save(self, *args, **kwargs):
        raise TypeError("El registro general se calcula en el backend; use los servicios del portal.")

    def delete(self, *args, **kwargs):
        raise TypeError("El registro general es de consulta.")

    def refresh_from_db(self):
        filtros = {"accion_id": self.accion_id} if self.accion_id is not None else {"fila_id": self.fila_id}
        actualizado = self.objects.get(**filtros)
        self.__dict__.update(actualizado.__dict__)
        return self

    @property
    def valores(self):
        salida = []
        for nombre, _ in COLUMNAS_REGISTRO:
            valor = getattr(self, nombre)
            if isinstance(valor, datetime):
                valor = timezone.localtime(valor).strftime("%d/%m/%Y %H:%M")
            elif isinstance(valor, date):
                valor = valor.strftime("%d/%m/%Y")
            salida.append("" if valor is None else valor)
        return salida
