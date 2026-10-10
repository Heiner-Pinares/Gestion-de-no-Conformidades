from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO, StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.models import Usuario
from apps.catalogos.models import ConfiguracionUrgencia, FuenteDeteccion, MatrizPrioridad, PreguntaCausa, Proceso, TipoRegistro, Urgencia
from apps.hallazgos.forms import HallazgoForm
from apps.hallazgos.models import Accion, CorrelativoSAC, Hallazgo, HistorialHallazgo, Notificacion
from apps.hallazgos.selectors import acciones_disponibles, hallazgos_visibles, timeline_hallazgo
from apps.hallazgos.services import AccionService, CausaService, ComunicacionService, EficaciaService, EvidenciaService, HallazgoService, PBIService, WorkflowService
from apps.hallazgos.services.hallazgo import CodigoSACService, ImpactoService, PrioridadService


def preparar():
    call_command('seed_initial_data', stdout=StringIO())
    usuarios = []
    for nombre, rol in [('reportante','USUARIO'), ('calidad','VALIDADOR'), ('administrador','ADMINISTRADOR'), ('ajeno','USUARIO')]:
        u = Usuario.objects.create_user(nombre, password='ClaveSoloParaTests-2026!')
        u.add_role(rol)
        usuarios.append(u)
    proceso = Proceso.objects.create(nombre='Proceso de prueba', responsable=usuarios[0])
    proceso.validadores.add(usuarios[1])
    return (*usuarios, proceso)


class Recorridos(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario, cls.calidad, cls.admin, cls.ajeno, cls.proceso = preparar()

    def datos(self, **extras):
        d = dict(titulo='Hallazgo de prueba', tipo_registro=TipoRegistro.objects.get(codigo='INC'), fuente_deteccion=FuenteDeteccion.objects.get(codigo='OPERACION'), proceso=self.proceso, responsable=self.usuario, descripcion='Desviación del procedimiento', fecha_deteccion=timezone.now(), fecha_solucion=timezone.localdate()+timedelta(days=10), impacto_clientes=1, impacto_tiempo=2, impacto_soles=1, urgencia=Urgencia.objects.get(valor=2), es_critica='NO', criterio_categoria='Sin impacto crítico según revisión', requisito_referencia='Procedimiento P-001')
        d.update(extras)
        return d

    def crear(self, **extras):
        return HallazgoService.crear(usuario=self.usuario, datos=self.datos(**extras))

    def paso(self,h,accion,usuario=None,comentario='Motivo documentado'):
        nuevo = WorkflowService.ejecutar(usuario=usuario or self.usuario,hallazgo=h,accion=accion,comentario=comentario)
        h.refresh_from_db()
        return nuevo

    def accion(self,h,tipo='INMEDIATA'):
        return AccionService.crear(usuario=self.usuario,hallazgo=h,datos=dict(tipo=tipo,descripcion='Restablecer condición',responsable=self.usuario,fecha_inicio=timezone.localdate(),fet_inicial=timezone.localdate()+timedelta(days=2),resultado_esperado='Condición restablecida',comentario=''))

    def completar(self,a):
        return AccionService.seguir(usuario=self.usuario,accion=a,datos=dict(estado='COMPLETADA',porcentaje_avance=100,fecha_real=timezone.localdate(),comentario='Comprobado con evidencia'))

    def inmediata(self,h):
        self.paso(h,'enviar');self.paso(h,'validar',self.calidad);self.paso(h,'iniciar_inmediata')
        a=self.accion(h);self.completar(a)
        ComunicacionService.registrar(usuario=self.usuario,hallazgo=h,datos=dict(destinatarios='Responsable del proceso',medio='Reunión',descripcion='Comunicación de corrección',fecha=timezone.now()))
        return a

    def analizar(self,h):
        self.paso(h,'iniciar_analisis')
        preguntas = [p for p in PreguntaCausa.objects.all() if p.texto.strip().rstrip(':').casefold() != 'otro']
        return CausaService.guardar(usuario=self.usuario,hallazgo=h,datos=dict(causa_raiz='Falta de control preventivo',respuestas=[dict(pregunta=p,respuesta='NO',comentario='Revisado') for p in preguntas],control={}),finalizar=True)

    def verificar(self,h):
        self.paso(h,'enviar_verificacion')
        return EficaciaService.evaluar(usuario=self.calidad,hallazgo=h,datos=dict(fecha_evaluacion=timezone.localdate(),resultado='EFICAZ',comentario='No se repite la desviación'))

    def test_no_critica_recorrido_completo(self):
        h=self.crear(); self.inmediata(h); self.verificar(h); self.paso(h,'cerrar',self.admin)
        self.assertEqual(h.estado,'CERRADO')
        self.assertEqual(h.ciclos.filter(fecha_cierre__isnull=False).count(),1)
        self.assertEqual(sum(p['estado']=='No aplica' for p in timeline_hallazgo(h)),1)
        with self.assertRaises(ValidationError): self.accion(h)

    def test_historial_del_hallazgo_usa_linea_de_tiempo_estructurada(self):
        h = self.crear()
        HistorialHallazgo.objects.create(
            hallazgo=h,
            usuario=self.calidad,
            accion='EVALUACION_EFICACIA',
            estado_anterior='EN_VERIFICACION',
            estado_nuevo='EN_VERIFICACION',
            comentario='La solución eliminó la recurrencia.',
            metadata_json={'resultado': 'EFICAZ', 'ciclo': 1, 'evaluacion': 70000475},
        )
        HistorialHallazgo.objects.create(
            hallazgo=h,
            usuario=self.usuario,
            accion='ENVIAR_VERIFICACION',
            estado_anterior='ACCION_INMEDIATA',
            estado_nuevo='EN_VERIFICACION',
        )
        self.client.force_login(self.admin)

        respuesta = self.client.get(reverse('hallazgo_detalle', args=[h.pk]))

        self.assertContains(respuesta, 'finding-timeline')
        self.assertContains(respuesta, f'{h.historial.count()} registros')
        self.assertContains(respuesta, 'tag-eficaz')
        self.assertContains(respuesta, '70000475')
        self.assertContains(respuesta, 'ACCION_INMEDIATA')
        self.assertContains(respuesta, 'EN_VERIFICACION')
        self.assertNotContains(respuesta, 'Detalle registrado')
        self.assertNotContains(respuesta, 'audit-data')

    def test_cierre_exige_visto_bueno_del_administrador(self):
        h = self.crear()
        self.inmediata(h)
        self.verificar(h)
        h.refresh_from_db()

        with self.assertRaises(PermissionDenied):
            self.paso(h, 'cerrar', self.calidad)
        self.assertNotIn('cerrar', dict(acciones_disponibles(self.calidad, h)))
        self.assertEqual(
            dict(acciones_disponibles(self.admin, h))['cerrar'],
            'Dar visto bueno y cerrar',
        )

        self.client.force_login(self.admin)
        detalle = self.client.get(reverse('hallazgo_detalle', args=[h.pk]))
        self.assertContains(detalle, 'Visto bueno administrativo y cierre')
        self.assertContains(detalle, 'Dar visto bueno y cerrar')
        respuesta = self.client.post(reverse('hallazgo_transicion', args=[h.pk, 'cerrar']), {
            'comentario': 'Expediente revisado y conforme para el cierre.',
            'version': h.version,
            'confirmar': 'on',
        })
        self.assertEqual(respuesta.url, reverse('hallazgo_detalle', args=[h.pk]))
        h.refresh_from_db()
        self.assertEqual(h.estado, 'CERRADO')
        self.assertEqual(h.ciclo_actual.responsable_cierre, self.admin)
        self.assertEqual(h.ciclo_actual.resultado_cierre, 'EFICAZ')

    def test_paso_cuatro_exige_todas_las_actividades_completadas_al_cien(self):
        h=self.crear(); self.paso(h,'enviar'); self.paso(h,'validar',self.calidad); self.paso(h,'iniciar_inmediata')
        actividad=self.accion(h)
        with self.assertRaisesRegex(ValidationError, 'todas las actividades al 100'):
            self.paso(h,'enviar_verificacion')
        h.refresh_from_db()
        self.assertEqual(h.estado, 'ACCION_INMEDIATA')
        self.assertFalse(h.ciclo_actual.evaluaciones.exists())

        # La misma regla protege el servicio aunque un estado histórico haya
        # quedado manualmente en verificación.
        Hallazgo.objects.filter(pk=h.pk).update(estado='EN_VERIFICACION')
        h.refresh_from_db()
        with self.assertRaisesRegex(ValidationError, 'todas las actividades al 100'):
            EficaciaService.evaluar(usuario=self.calidad,hallazgo=h,datos=dict(
                fecha_evaluacion=timezone.localdate(),resultado='EFICAZ',comentario='Intento anticipado'))

        Hallazgo.objects.filter(pk=h.pk).update(estado='ACCION_INMEDIATA')
        h.refresh_from_db()
        self.completar(actividad)
        self.paso(h,'enviar_verificacion')
        EficaciaService.evaluar(usuario=self.calidad,hallazgo=h,datos=dict(
            fecha_evaluacion=timezone.localdate(),resultado='EFICAZ',comentario='Todas las actividades están completadas'))
        self.paso(h,'cerrar',self.admin)
        self.assertEqual(h.estado,'CERRADO')

    def test_plan_incluye_accion_inmediata_estados_y_confirmacion(self):
        h = self.crear()
        self.paso(h, 'enviar')
        self.paso(h, 'validar', self.calidad)
        self.paso(h, 'iniciar_inmediata')
        self.client.force_login(self.usuario)

        pantalla = self.client.get(reverse('hallazgo_accion', args=[h.pk]))
        self.assertContains(pantalla, 'value="INMEDIATA"')
        self.assertContains(pantalla, 'Solución inmediata')
        self.assertContains(pantalla, 'value="CORRECTIVA"')
        self.assertContains(pantalla, 'Acción correctiva')
        self.assertNotContains(pantalla, 'value="ACCION_INMEDIATA"')
        self.assertContains(pantalla, 'Código de actividad')
        self.assertContains(pantalla, 'Responsable AC')
        self.assertContains(pantalla, 'FET compromiso')
        self.assertContains(pantalla, 'activity-section-heading')
        self.assertContains(pantalla, 'activity-field--code')
        for nombre in ('descripcion', 'tipo', 'responsable', 'fet_inicial', 'estado'):
            self.assertTrue(pantalla.context['formset'].forms[0].fields[nombre].required)
        for codigo, etiqueta in Accion.ESTADOS:
            self.assertContains(pantalla, f'value="{codigo}"')
            self.assertContains(pantalla, etiqueta)
        self.assertContains(pantalla, '¿Enviar actividades?')
        self.assertContains(pantalla, 'Estas actividades se enviarán a tu jefe para su revisión.')
        self.assertContains(pantalla, 'data-confirm-activities')

        incompleto = {
            'actividades-TOTAL_FORMS': '1', 'actividades-INITIAL_FORMS': '0',
            'actividades-MIN_NUM_FORMS': '1', 'actividades-MAX_NUM_FORMS': '1000',
            'actividades-0-tipo': 'INMEDIATA',
            'actividades-0-descripcion': '',
            'actividades-0-responsable': '', 'actividades-0-fet_inicial': '',
            'actividades-0-estado': '',
        }
        respuesta_incompleta = self.client.post(reverse('hallazgo_accion', args=[h.pk]), incompleto)
        self.assertEqual(respuesta_incompleta.status_code, 200)
        self.assertContains(respuesta_incompleta, 'Este campo es obligatorio.', count=4)
        self.assertFalse(h.ciclo_actual.acciones.exists())

        plan = {
            'actividades-TOTAL_FORMS': '2', 'actividades-INITIAL_FORMS': '0',
            'actividades-MIN_NUM_FORMS': '1', 'actividades-MAX_NUM_FORMS': '1000',
            'actividades-0-tipo': 'INMEDIATA',
            'actividades-0-descripcion': 'Restablecer el servicio',
            'actividades-0-responsable': self.usuario.pk,
            'actividades-0-fet_inicial': timezone.localdate().isoformat(),
            'actividades-0-estado': 'PENDIENTE',
            'actividades-1-tipo': 'CORRECTIVA',
            'actividades-1-descripcion': 'Comunicar la contingencia',
            'actividades-1-responsable': self.usuario.pk,
            'actividades-1-fet_inicial': (timezone.localdate() + timedelta(days=1)).isoformat(),
            'actividades-1-estado': 'EN_PROCESO',
        }
        respuesta = self.client.post(reverse('hallazgo_accion', args=[h.pk]), plan)
        self.assertEqual(respuesta.url, reverse('hallazgo_acciones_creadas', args=[h.pk]))
        adicional = h.ciclo_actual.acciones.get(tipo='CORRECTIVA')
        self.assertEqual((adicional.get_tipo_display(), adicional.estado, adicional.porcentaje_avance),
                         ('Acción correctiva', 'EN_PROCESO', 50))

    def test_puede_agregar_compromisos_durante_la_implementacion(self):
        h = self.crear(es_critica='SI')
        self.inmediata(h)
        self.analizar(h)
        self.paso(h, 'planificar')
        self.accion(h, 'CORRECTIVA')
        self.paso(h, 'iniciar_implementacion')
        self.client.force_login(self.usuario)

        detalle = self.client.get(reverse('hallazgo_detalle', args=[h.pk]))
        self.assertContains(detalle, '＋ Agregar compromiso')
        pantalla = self.client.get(reverse('hallazgo_accion', args=[h.pk]))
        self.assertContains(pantalla, 'Agregar compromisos')
        self.assertContains(pantalla, 'data-next-number="3"')

        respuesta = self.client.post(reverse('hallazgo_accion', args=[h.pk]), {
            'actividades-TOTAL_FORMS': '1', 'actividades-INITIAL_FORMS': '0',
            'actividades-MIN_NUM_FORMS': '1', 'actividades-MAX_NUM_FORMS': '1000',
            'actividades-0-tipo': 'CORRECTIVA',
            'actividades-0-descripcion': 'Capacitar al equipo responsable',
            'actividades-0-responsable': self.usuario.pk,
            'actividades-0-fet_inicial': (timezone.localdate() + timedelta(days=3)).isoformat(),
            'actividades-0-estado': 'PENDIENTE',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse('hallazgo_acciones_creadas', args=[h.pk]))
        h.refresh_from_db()
        self.assertEqual(h.estado, 'EN_IMPLEMENTACION')
        self.assertTrue(h.ciclo_actual.acciones.filter(
            codigo=f'{h.codigo}-A03', descripcion='Capacitar al equipo responsable',
        ).exists())

    def test_plan_exige_tipos_minimos_segun_criticidad(self):
        fecha = (timezone.localdate() + timedelta(days=2)).isoformat()
        base = {
            'actividades-TOTAL_FORMS': '1', 'actividades-INITIAL_FORMS': '0',
            'actividades-MIN_NUM_FORMS': '1', 'actividades-MAX_NUM_FORMS': '1000',
            'actividades-0-descripcion': 'Atender el hallazgo',
            'actividades-0-responsable': self.usuario.pk,
            'actividades-0-fet_inicial': fecha,
            'actividades-0-estado': 'PENDIENTE',
        }

        critico = self.crear(es_critica='SI')
        self.paso(critico, 'enviar')
        self.paso(critico, 'validar', self.calidad)
        self.paso(critico, 'iniciar_inmediata')
        self.client.force_login(self.usuario)
        solo_inmediata = dict(base, **{'actividades-0-tipo': 'INMEDIATA'})
        respuesta = self.client.post(reverse('hallazgo_accion', args=[critico.pk]), solo_inmediata)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'una Solución inmediata y una Acción correctiva')
        self.assertFalse(critico.ciclo_actual.acciones.exists())

        plan_critico = {
            'actividades-TOTAL_FORMS': '2', 'actividades-INITIAL_FORMS': '0',
            'actividades-MIN_NUM_FORMS': '1', 'actividades-MAX_NUM_FORMS': '1000',
            'actividades-0-tipo': 'INMEDIATA',
            'actividades-0-descripcion': 'Contener el impacto',
            'actividades-0-responsable': self.usuario.pk,
            'actividades-0-fet_inicial': fecha,
            'actividades-0-estado': 'PENDIENTE',
            'actividades-1-tipo': 'CORRECTIVA',
            'actividades-1-descripcion': 'Eliminar la causa',
            'actividades-1-responsable': self.usuario.pk,
            'actividades-1-fet_inicial': fecha,
            'actividades-1-estado': 'PENDIENTE',
        }
        respuesta = self.client.post(reverse('hallazgo_accion', args=[critico.pk]), plan_critico)
        self.assertEqual(respuesta.url, reverse('hallazgo_acciones_creadas', args=[critico.pk]))
        self.assertEqual(set(critico.ciclo_actual.acciones.values_list('tipo', flat=True)), {'INMEDIATA', 'CORRECTIVA'})

        no_critico = self.crear(es_critica='NO')
        self.paso(no_critico, 'enviar')
        self.paso(no_critico, 'validar', self.calidad)
        self.paso(no_critico, 'iniciar_inmediata')
        solo_correctiva = dict(base, **{'actividades-0-tipo': 'CORRECTIVA'})
        respuesta = self.client.post(reverse('hallazgo_accion', args=[no_critico.pk]), solo_correctiva)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'debe incluir como mínimo una Solución inmediata')
        self.assertFalse(no_critico.ciclo_actual.acciones.exists())

    def test_cancelada_es_terminal_y_no_bloquea_el_paso_cuatro(self):
        h = self.crear()
        self.paso(h, 'enviar')
        self.paso(h, 'validar', self.calidad)
        self.paso(h, 'iniciar_inmediata')
        solucion = self.accion(h)
        adicional = self.accion(h, 'ACCION_INMEDIATA')
        self.completar(solucion)
        AccionService.seguir(
            usuario=self.usuario,
            accion=adicional,
            datos=dict(estado='CANCELADA', porcentaje_avance=0, fecha_real=None,
                       comentario='La actividad dejó de ser necesaria.'),
        )
        self.paso(h, 'enviar_verificacion')
        self.assertEqual(h.estado, 'EN_VERIFICACION')
        with self.assertRaisesRegex(ValidationError, 'terminada o cancelada'):
            AccionService.reprogramar(
                usuario=self.usuario,
                accion=adicional,
                nueva_fecha=timezone.localdate() + timedelta(days=1),
                motivo='No debe permitirse',
            )

        self.client.force_login(self.usuario)
        seguimiento = self.client.get(reverse('hallazgo_acciones_seguimiento', args=[h.pk]))
        self.assertContains(seguimiento, 'data-activity-scrollbar')
        self.assertContains(seguimiento, 'data-activity-scroll')
        self.assertContains(seguimiento, 'Cancelada')

    def test_modal_de_seguimiento_actualiza_avance_y_adjunta_evidencia(self):
        h = self.crear()
        self.paso(h, 'enviar')
        self.paso(h, 'validar', self.calidad)
        self.paso(h, 'iniciar_inmediata')
        actividad = self.accion(h)
        self.client.force_login(self.usuario)

        detalle = self.client.get(reverse('hallazgo_detalle', args=[h.pk]))
        self.assertContains(detalle, 'data-follow-modal')
        self.assertContains(detalle, 'data-follow-open')
        self.assertContains(detalle, 'Seguimiento de la acción')
        self.assertContains(detalle, 'Adjuntar evidencia')
        self.assertContains(detalle, 'Sin asignar', count=0)
        self.assertContains(detalle, 'Compromisos · Plan 1')
        self.assertContains(detalle, 'Plan actual:')
        self.assertContains(detalle, 'Plan 1 ·')
        self.assertNotContains(detalle, 'Compromisos · Ciclo')
        self.assertNotContains(detalle, 'Ciclo actual:')
        self.assertNotContains(detalle, 'Ciclo 1')
        self.assertContains(detalle, 'F. registro')
        self.assertContains(detalle, 'F. compromiso')
        self.assertContains(detalle, 'Evidencias')
        self.assertContains(detalle, 'commitments-scroll')
        self.assertNotContains(detalle, 'Tratamiento · Ciclo 1')

        respuesta = self.client.post(reverse('accion_seguimiento', args=[actividad.pk]), {
            'porcentaje_avance': '70',
            'comentario': 'Se implementaron los controles preventivos y se inició la validación.',
        })
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse('hallazgo_detalle', args=[h.pk]))
        actividad.refresh_from_db()
        self.assertEqual((actividad.estado, actividad.porcentaje_avance), ('EN_PROCESO', 70))
        seguimiento = actividad.seguimientos.get()
        self.assertEqual(seguimiento.metadata_json['avance'], 70)

        detalle_historial = self.client.get(reverse('hallazgo_detalle', args=[h.pk]))
        self.assertContains(detalle_historial, 'Historial (1)')
        self.assertContains(detalle_historial, 'data-history-open')
        self.assertContains(detalle_historial, 'data-history-modal')
        self.assertContains(detalle_historial, 'Ver detalle')
        bloque_historial = detalle_historial.content.decode().split(
            '<details class="commitment-history">', 1
        )[1].split('</details>', 1)[0]
        self.assertNotIn('<p>', bloque_historial)
        self.assertIn('data-history-comment="Se implementaron los controles preventivos', bloque_historial)

        pdf = SimpleUploadedFile('control_procesos.pdf', b'%PDF-1.4\ncontenido\n%%EOF', content_type='application/pdf')
        with TemporaryDirectory() as carpeta, override_settings(MEDIA_ROOT=carpeta):
            respuesta = self.client.post(reverse('accion_seguimiento', args=[actividad.pk]), {
                'porcentaje_avance': '100',
                'comentario': 'Actividad terminada y comprobada con evidencia.',
                'archivo': pdf,
            })
            self.assertEqual(respuesta.status_code, 302)
            actividad.refresh_from_db()
            self.assertEqual((actividad.estado, actividad.porcentaje_avance), ('COMPLETADA', 100))
            evidencia = actividad.evidencias.get()
            self.assertEqual(evidencia.nombre_original, 'control_procesos.pdf')
            self.assertEqual(evidencia.hallazgo_id, h.pk)
            seguimiento_final = actividad.seguimientos.first()
            self.assertEqual(seguimiento_final.metadata_json['evidencia_ids'], [evidencia.pk])

            # Los archivos históricos anteriores al enlace explícito se recuperan
            # por el comentario del seguimiento al que fueron adjuntados.
            metadata = dict(seguimiento_final.metadata_json)
            metadata.pop('evidencia_ids')
            seguimiento_final.metadata_json = metadata
            seguimiento_final.save(update_fields=['metadata_json'])
            detalle = self.client.get(reverse('hallazgo_detalle', args=[h.pk]))
            self.assertContains(detalle, 'Documento adjunto')
            self.assertContains(detalle, 'control_procesos.pdf')
            self.assertContains(detalle, f'{reverse("evidencia_descargar", args=[evidencia.pk])}?ver=1')
            self.assertNotContains(detalle, '<h2 class="plain">Evidencias</h2>', html=True)
            self.assertNotContains(detalle, 'Ver evidencias')

    def test_seguimiento_modal_rechaza_reducir_el_avance(self):
        h = self.crear()
        self.paso(h, 'enviar'); self.paso(h, 'validar', self.calidad); self.paso(h, 'iniciar_inmediata')
        actividad = self.accion(h)
        AccionService.seguir(usuario=self.usuario, accion=actividad, datos={
            'estado': 'EN_PROCESO', 'porcentaje_avance': 60, 'fecha_real': None,
            'comentario': 'Avance inicial comprobado.',
        })
        self.client.force_login(self.usuario)
        respuesta = self.client.post(reverse('accion_seguimiento', args=[actividad.pk]), {
            'porcentaje_avance': '40', 'comentario': 'Intento de reducción.',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'El nuevo avance no puede ser menor que el avance actual.')
        actividad.refresh_from_db()
        self.assertEqual(actividad.porcentaje_avance, 60)

    def test_reprogramacion_solicita_aprobacion_con_evidencia_y_solo_cambia_al_aprobar(self):
        h = self.crear()
        self.paso(h, 'enviar'); self.paso(h, 'validar', self.calidad); self.paso(h, 'iniciar_inmediata')
        actividad = self.accion(h)
        fecha_original = actividad.fecha_vigente
        propuesta = timezone.localdate() + timedelta(days=5)
        self.ajeno.first_name = 'María'
        self.ajeno.last_name = 'Gómez'
        self.ajeno.cargo = 'Jefe de Operaciones'
        self.ajeno.save(update_fields=['first_name', 'last_name', 'cargo'])
        self.client.force_login(self.usuario)

        detalle = self.client.get(reverse('hallazgo_detalle', args=[h.pk]))
        self.assertContains(detalle, 'data-reprogram-modal')
        self.assertContains(detalle, 'data-reprogram-open')
        self.assertContains(detalle, 'Solicitar reprogramación')
        self.assertContains(detalle, 'debe ser aprobada por el responsable de cada jefatura')
        self.assertContains(detalle, 'Responsable de jefatura que aprobará')
        self.assertContains(detalle, 'PDF, DOC, DOCX, XLS, XLSX, JPG, PNG')

        pdf = SimpleUploadedFile('sustento.pdf', b'%PDF-1.4\nsustento\n%%EOF', content_type='application/pdf')
        with TemporaryDirectory() as carpeta, override_settings(MEDIA_ROOT=carpeta):
            respuesta = self.client.post(reverse('accion_reprogramar', args=[actividad.pk]), {
                'nueva_fecha': propuesta.isoformat(),
                'motivo': 'Se requiere ampliar el plazo para completar la validación.',
                'aprobador': self.ajeno.pk,
                'archivo': pdf,
            })
            self.assertEqual(respuesta.status_code, 302)
            self.assertEqual(respuesta.url, reverse('hallazgo_detalle', args=[h.pk]))
            actividad.refresh_from_db()
            self.assertEqual(actividad.fecha_vigente, fecha_original)
            solicitud = actividad.eventos.get(accion='SOLICITUD_REPROGRAMACION')
            self.assertEqual(solicitud.metadata_json['estado'], 'PENDIENTE')
            self.assertEqual(solicitud.metadata_json['aprobador_id'], self.ajeno.pk)
            self.assertTrue(solicitud.metadata_json['evidencia_id'])
            self.assertTrue(self.ajeno.notificaciones.filter(tipo='aprobacion_reprogramacion').exists())

            self.client.force_login(self.calidad)
            no_autorizada = self.client.post(reverse('accion_reprogramacion_resolver', args=[solicitud.pk, 'aprobar']))
            self.assertEqual(no_autorizada.status_code, 403)
            actividad.refresh_from_db(); solicitud.refresh_from_db()
            self.assertEqual(actividad.fecha_vigente, fecha_original)
            self.assertEqual(solicitud.metadata_json['estado'], 'PENDIENTE')

            self.client.force_login(self.ajeno)
            revision = self.client.get(reverse('hallazgo_detalle', args=[h.pk]))
            self.assertEqual(revision.status_code, 200)
            self.assertContains(revision, 'Reprogramación pendiente')
            self.assertContains(revision, 'Aprobar')
            self.assertContains(revision, 'Rechazar')
            aprobacion = self.client.post(reverse('accion_reprogramacion_resolver', args=[solicitud.pk, 'aprobar']))
            self.assertEqual(aprobacion.status_code, 302)
            self.assertEqual(self.client.get(aprobacion.url).status_code, 200)

        actividad.refresh_from_db(); solicitud.refresh_from_db()
        self.assertEqual(actividad.fecha_vigente, propuesta)
        self.assertEqual(solicitud.metadata_json['estado'], 'APROBADA')
        self.assertEqual(actividad.reprogramaciones.count(), 1)
        self.assertTrue(self.usuario.notificaciones.filter(tipo='reprogramacion_aprobada').exists())

        self.client.force_login(self.usuario)
        segunda_fecha = propuesta + timedelta(days=1)
        self.client.post(reverse('accion_reprogramar', args=[actividad.pk]), {
            'nueva_fecha': segunda_fecha.isoformat(), 'motivo': 'Segunda solicitud para comprobar rechazo.',
            'aprobador': self.ajeno.pk,
        })
        segunda = actividad.eventos.filter(
            accion='SOLICITUD_REPROGRAMACION', metadata_json__estado='PENDIENTE',
        ).get()
        self.client.force_login(self.ajeno)
        rechazo = self.client.post(reverse('accion_reprogramacion_resolver', args=[segunda.pk, 'rechazar']))
        self.assertEqual(rechazo.status_code, 302)
        self.assertEqual(self.client.get(rechazo.url).status_code, 200)
        actividad.refresh_from_db(); segunda.refresh_from_db()
        self.assertEqual(actividad.fecha_vigente, propuesta)
        self.assertEqual(segunda.metadata_json['estado'], 'RECHAZADA')
        self.assertEqual(actividad.reprogramaciones.count(), 1)

    def test_critica_tecnologica_exige_6m_pbi_y_correctivas(self):
        h=self.crear(es_critica='SI',origen_tecnologico=True); self.inmediata(h)
        with self.assertRaises(ValidationError): self.paso(h,'enviar_verificacion')
        self.analizar(h)
        with self.assertRaises(ValidationError): self.paso(h,'planificar')
        self.paso(h,'iniciar_pbi')
        with self.assertRaises(ValidationError): self.paso(h,'planificar')
        PBIService.guardar(usuario=self.usuario,hallazgo=h,datos=dict(numero_pbi='PBI-TEST',sistema='Facturación',responsable_ti=self.usuario,estado='ABIERTO',fecha_cierre=None))
        self.paso(h,'planificar'); a=self.accion(h,'CORRECTIVA'); self.paso(h,'iniciar_implementacion'); self.completar(a)
        self.verificar(h);self.paso(h,'cerrar',self.admin)
        self.assertEqual(h.estado,'CERRADO')
        self.assertEqual(len(h.ciclo_actual.respuestas),26)

    def test_devolucion_correccion_y_reenvio(self):
        h=self.crear();self.paso(h,'enviar')
        with self.assertRaises(ValidationError): self.paso(h,'devolver',self.calidad,comentario='')
        self.paso(h,'devolver',self.calidad)
        HallazgoService.actualizar(usuario=self.usuario,hallazgo=h,datos={'descripcion':'Descripción corregida'},version=h.version)
        self.paso(h,'enviar');self.assertEqual(h.estado,'PENDIENTE_VALIDACION')
        self.assertTrue(h.historial.filter(accion='DEVOLVER').exists())

    def test_no_eficaz_preserva_ciclo_y_reabre(self):
        h=self.crear(); anterior=self.inmediata(h); self.paso(h,'enviar_verificacion')
        EficaciaService.evaluar(usuario=self.calidad,hallazgo=h,datos=dict(fecha_evaluacion=timezone.localdate(),resultado='NO_EFICAZ',comentario='La falla volvió a ocurrir'))
        h.refresh_from_db();self.assertEqual(h.estado,'REABIERTO');self.assertEqual(h.ciclos.count(),2)
        self.assertEqual(h.es_critica,'NO')
        with self.assertRaises(ValidationError): AccionService.reprogramar(usuario=self.usuario,accion=anterior,nueva_fecha=timezone.localdate()+timedelta(days=20),motivo='No permitido')
        self.paso(h,'iniciar_inmediata');self.completar(self.accion(h))
        ComunicacionService.registrar(usuario=self.usuario,hallazgo=h,datos=dict(destinatarios='Equipo',medio='Reunión',descripcion='Nueva corrección',fecha=timezone.now()))
        self.verificar(h);self.paso(h,'cerrar',self.admin)
        self.assertEqual(h.ciclos.first().evaluaciones.first().resultado,'NO_EFICAZ')

    def test_reapertura_manual_no_borra_cierre(self):
        h=self.crear();self.inmediata(h);self.verificar(h);self.paso(h,'cerrar',self.admin);self.paso(h,'reabrir',self.calidad)
        self.assertEqual(h.ciclos.filter(fecha_cierre__isnull=False).count(),1);self.assertEqual(h.ciclos.count(),2)

    def test_reprogramaciones_maximo_y_fet_inmutable(self):
        h=self.crear();self.paso(h,'enviar');self.paso(h,'validar',self.calidad);self.paso(h,'iniciar_inmediata');a=self.accion(h);fet=a.fet_inicial
        for dias in [3,4,5]: AccionService.reprogramar(usuario=self.usuario,accion=a,nueva_fecha=timezone.localdate()+timedelta(days=dias),motivo='Justificación')
        with self.assertRaises(ValidationError): AccionService.reprogramar(usuario=self.usuario,accion=a,nueva_fecha=timezone.localdate()+timedelta(days=6),motivo='Cuarta')
        a.refresh_from_db();self.assertEqual(a.fet_inicial,fet);self.assertEqual(a.reprogramaciones.count(),3)

    def test_roles_y_aislamiento(self):
        h=self.crear();self.paso(h,'enviar')
        for u in [self.usuario,self.admin,self.ajeno]:
            with self.assertRaises(PermissionDenied): self.paso(h,'validar',u)
        self.assertFalse(hallazgos_visibles(self.ajeno).filter(pk=h.pk).exists())
        self.assertTrue(hallazgos_visibles(self.admin).filter(pk=h.pk).exists())
        otro=Proceso.objects.create(nombre='Fuera de alcance');h2=self.crear(proceso=otro);self.paso(h2,'enviar')
        with self.assertRaises(PermissionDenied): self.paso(h2,'validar',self.calidad)
        with self.assertRaises(PermissionDenied): HallazgoService.actualizar(usuario=self.ajeno,hallazgo=h,datos={'titulo':'Intrusión'})

    def test_no_autovalidacion_multirrol(self):
        self.usuario.add_role('VALIDADOR');self.proceso.validadores.add(self.usuario)
        self.usuario=Usuario.objects.get(pk=self.usuario.pk)
        h=self.crear();self.paso(h,'enviar')
        with self.assertRaises(PermissionDenied): self.paso(h,'validar',self.usuario)

    def test_sac_unico_y_tipo_protegido_fuera_del_analisis(self):
        h=self.crear();h2=self.crear();self.assertNotEqual(h.codigo,h2.codigo)
        self.assertRegex(h.codigo,r'^SAC-INC-\d{4}-\d{4}$')
        with self.assertRaises(ValidationError): HallazgoService.actualizar(usuario=self.usuario,hallazgo=h,datos={'tipo_registro':TipoRegistro.objects.get(codigo='NOC')})
        with self.assertRaises(IntegrityError), transaction.atomic(): Hallazgo.objects.filter(pk=h2.pk).update(codigo=h.codigo)
        with override_settings(SAC_SEQUENCE_SCOPE='YEAR'), self.assertRaises(ValidationError): self.crear()

    def test_fecha_impacto_prioridad_y_na(self):
        with self.assertRaises(ValidationError): self.crear(fecha_solucion=timezone.localdate()-timedelta(days=1))
        self.assertEqual(ImpactoService.calcular(clientes=1,tiempo=3,soles=2),3)
        for v in [0,4,True]:
            with self.assertRaises(ValidationError): ImpactoService.calcular(clientes=v,tiempo=2,soles=1)
        MatrizPrioridad.objects.filter(impacto__valor=2,urgencia__valor=2).update(activo=False)
        with self.assertRaises(ValidationError): self.crear()
        h=self.crear(aplica_impacto=False,justificacion_no_impacto='Hallazgo documental');self.assertIsNone(h.prioridad)
        with self.assertRaises(ValidationError): self.crear(aplica_impacto=False,origen_tecnologico=True,justificacion_no_impacto='No permitido')
        h=self.crear(aplica_impacto=False,justificacion_no_impacto='Documental',es_critica='NA')
        with self.assertRaises(ValidationError): self.paso(h,'enviar')

    def test_prioridad_critica_fuerza_criticidad_y_las_demas_permiten_elegir(self):
        urgencia_alta = Urgencia.objects.get(valor=3)
        critico = self.crear(
            impacto_clientes=3, impacto_tiempo=3, impacto_soles=3,
            urgencia=urgencia_alta, es_critica='NO',
        )
        self.assertEqual(critico.prioridad.codigo, 'CRITICA')
        self.assertEqual(critico.es_critica, 'SI')

        no_critico = self.crear(es_critica='NO')
        self.assertNotEqual(no_critico.prioridad.codigo, 'CRITICA')
        self.assertEqual(no_critico.es_critica, 'NO')

        self.client.force_login(self.usuario)
        pantalla = self.client.get(reverse('hallazgo_crear'))
        self.assertContains(pantalla, 'id="criticidadForzada"')
        self.assertContains(pantalla, 'La prioridad Crítica establece automáticamente')
        self.assertContains(pantalla, '"es_critica": true')

    def test_no_saltos_ni_cierre_sin_eficacia(self):
        h=self.crear()
        with self.assertRaises(ValidationError): self.paso(h,'cerrar',self.admin)
        self.paso(h,'enviar');self.paso(h,'validar',self.calidad);self.paso(h,'iniciar_inmediata');self.completar(self.accion(h))
        self.paso(h,'enviar_verificacion')
        with self.assertRaises(ValidationError): self.paso(h,'cerrar',self.admin)

    def test_control_6m_obligatorio_y_snapshot(self):
        h=self.crear(es_critica='SI');self.inmediata(h);self.paso(h,'iniciar_analisis')
        preguntas = [p for p in PreguntaCausa.objects.all() if p.texto.strip().rstrip(':').casefold() != 'otro']
        respuestas=[dict(pregunta=p,respuesta='SI' if p.pk=='4.1' else 'NO',comentario='') for p in preguntas]
        with self.assertRaises(ValidationError): CausaService.guardar(usuario=self.usuario,hallazgo=h,datos=dict(causa_raiz='Causa',respuestas=respuestas,control={}),finalizar=True)
        control=dict(tipos=['PREVENTIVO'],nombre='Control',descripcion='Validación',mitiga_riesgo='SI',frecuencia='Diaria',responsable='Equipo',evidencia='Documento de control')
        a=CausaService.guardar(usuario=self.usuario,hallazgo=h,datos=dict(causa_raiz='Causa',respuestas=respuestas,control=control),finalizar=True)
        texto=next(r['texto_snapshot'] for r in a.respuestas if r['pregunta_id']=='1.1')
        PreguntaCausa.objects.filter(pk='1.1').update(texto='Nueva pregunta')
        self.assertEqual(next(r['texto_snapshot'] for r in a.respuestas if r['pregunta_id']=='1.1'),texto)

    def test_version_y_atomicidad(self):
        h=self.crear();version=h.version;self.paso(h,'enviar')
        with self.assertRaises(ValidationError): WorkflowService.ejecutar(usuario=self.calidad,hallazgo=h,accion='validar',version=version)
        n=h.historial.count()
        with patch('apps.hallazgos.services.common.Notificacion.objects.bulk_create',side_effect=RuntimeError('fallo de prueba')), self.assertRaises(RuntimeError): self.paso(h,'validar',self.calidad)
        h.refresh_from_db();self.assertEqual(h.estado,'PENDIENTE_VALIDACION');self.assertEqual(h.historial.count(),n)

    def test_otro_6m_se_agrega_responde_y_deshace_sin_tabla_adicional(self):
        h=self.crear(es_critica='SI');self.inmediata(h);self.paso(h,'iniciar_analisis')
        self.client.force_login(self.usuario)
        pantalla = self.client.get(reverse('hallazgo_causa', args=[h.pk]))
        self.assertEqual(pantalla.status_code, 200)
        self.assertEqual(pantalla.content.decode().count('data-add-other'), 6)
        self.assertNotContains(pantalla, '>Otro:</span>')

        incompleto = self.client.post(reverse('hallazgo_causa', args=[h.pk]), {
            'a_1_6': '1', 't_1_6': '', 'r_1_6': '', 'c_1_6': '', 'finalizar': '0',
        })
        self.assertEqual(incompleto.status_code, 200)
        self.assertContains(incompleto, 'Escribe el punto o pregunta adicional.')

        guardado = self.client.post(reverse('hallazgo_causa', args=[h.pk]), {
            'a_1_6': '1', 't_1_6': '¿Existe una excepción documentada?',
            'r_1_6': 'NO', 'c_1_6': 'Debe formalizarse', 'finalizar': '0',
        })
        self.assertEqual(guardado.url, reverse('hallazgo_causa', args=[h.pk]))
        h.refresh_from_db()
        otro = next(r for r in h.ciclo_actual.respuestas if r['pregunta_id'] == '1.6')
        self.assertEqual(otro['texto_snapshot'], '¿Existe una excepción documentada?')
        self.assertEqual(otro['respuesta'], 'NO')
        self.assertTrue(otro['es_otro'])
        reapertura = self.client.get(reverse('hallazgo_causa', args=[h.pk]))
        self.assertContains(reapertura, '¿Existe una excepción documentada?')

        deshecho = self.client.post(reverse('hallazgo_causa', args=[h.pk]), {
            'a_1_6': '0', 't_1_6': '', 'r_1_6': '', 'c_1_6': '', 'finalizar': '0',
        })
        self.assertEqual(deshecho.url, reverse('hallazgo_causa', args=[h.pk]))
        h.refresh_from_db()
        self.assertFalse(any(r['pregunta_id'] == '1.6' for r in h.ciclo_actual.respuestas))

    def test_archivos_y_descarga_privada(self):
        h=self.crear();buf=BytesIO();Image.new('RGB',(2,2)).save(buf,format='PNG')
        with TemporaryDirectory() as carpeta, override_settings(MEDIA_ROOT=carpeta):
            e=EvidenciaService.subir(usuario=self.usuario,hallazgo=h,archivo=SimpleUploadedFile('foto.png',buf.getvalue(),content_type='text/html'))
            self.assertEqual(e.mime_type,'image/png');self.assertNotEqual(e.archivo.name.split('/')[-1],'foto.png')
            self.client.force_login(self.usuario);self.assertEqual(self.client.get(reverse('evidencia_descargar',args=[e.pk])).status_code,200)
            self.client.force_login(self.ajeno);self.assertEqual(self.client.get(reverse('evidencia_descargar',args=[e.pk])).status_code,404)
            for nombre,contenido in [('fake.png',b'<script>alert(1)</script>'),('mal.exe',b'exe')]:
                with self.assertRaises(ValidationError): EvidenciaService.subir(usuario=self.usuario,hallazgo=h,archivo=SimpleUploadedFile(nombre,contenido))

    def test_login_csrf_y_urls_por_rol(self):
        self.assertTrue(self.client.login(username='reportante',password='ClaveSoloParaTests-2026!'))
        h=self.crear()
        for url in ['/',reverse('hallazgo_crear'),reverse('hallazgo_buscar'),reverse('hallazgo_detalle',args=[h.pk]),reverse('hallazgo_editar',args=[h.pk]),reverse('notificaciones'),reverse('ayuda')]:
            self.assertEqual(self.client.get(url).status_code,200,url)
        self.assertEqual(self.client.get(reverse('usuarios')).status_code,403)
        self.assertEqual(self.client.get(reverse('validaciones_admin')).status_code,403)
        self.assertEqual(self.client.get(reverse('configuracion_impacto')).status_code,403)
        self.assertEqual(self.client.get(reverse('configuracion_urgencia')).status_code,403)
        self.client.force_login(self.calidad);self.assertEqual(self.client.get(reverse('usuarios')).status_code,403)
        self.client.force_login(self.admin)
        for url in ['/',reverse('hallazgo_buscar'),reverse('validaciones_admin'),reverse('usuarios'),reverse('catalogos'),reverse('configuracion_impacto'),reverse('configuracion_urgencia'),reverse('auditoria'),reverse('reportes'),reverse('usuario_crear'),reverse('catalogo_crear',args=['procesos'])]:
            self.assertEqual(self.client.get(url).status_code,200,url)
        self.assertContains(self.client.get('/'), 'Dashboard principal')
        self.assertContains(self.client.get(reverse('validaciones_admin')), 'vistos buenos administrativos')
        self.assertEqual(self.client.get(reverse('hallazgo_crear')).status_code,403)
        seguro=Client(enforce_csrf_checks=True);seguro.force_login(self.usuario)
        self.assertEqual(seguro.post(reverse('hallazgo_crear'),{}).status_code,403)
        self.assertEqual(self.client.get(reverse('logout')).status_code,405)

    def test_indicadores_usan_hallazgos_compromisos_anio_y_jefatura_reales(self):
        self.proceso.gerencia = 'Facturación'
        self.proceso.save(update_fields=['gerencia'])
        hallazgo = self.crear()
        self.paso(hallazgo, 'enviar')
        self.paso(hallazgo, 'validar', self.calidad)
        self.paso(hallazgo, 'iniciar_inmediata')
        pendiente = self.accion(hallazgo)
        en_proceso = self.accion(hallazgo, 'ACCION_INMEDIATA')
        AccionService.seguir(usuario=self.usuario, accion=en_proceso, datos={
            'estado': 'EN_PROCESO', 'porcentaje_avance': 50, 'fecha_real': None,
            'comentario': 'Avance verificado para el indicador.',
        })
        fecha = timezone.now().replace(month=2, day=15)
        Hallazgo.objects.filter(pk=hallazgo.pk).update(fecha_registro=fecha, estado='CERRADO')

        otro_proceso = Proceso.objects.create(
            nombre='Proceso de otra jefatura', gerencia='Operaciones', responsable=self.usuario,
        )
        fuera_del_filtro = self.crear(proceso=otro_proceso)
        Hallazgo.objects.filter(pk=fuera_del_filtro.pk).update(fecha_registro=fecha)

        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('reportes'), {
            'anio': fecha.year, 'jefatura': 'Facturación',
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['total_hallazgos'], 1)
        self.assertEqual(respuesta.context['hallazgos_cerrados'], 1)
        self.assertEqual(respuesta.context['tasa_cierre_hallazgos'], 100)
        self.assertEqual(respuesta.context['total_acciones'], 2)
        self.assertEqual(respuesta.context['acciones_cerradas'], 0)
        self.assertEqual(respuesta.context['meses'][1]['total'], 1)
        self.assertEqual(respuesta.context['hallazgos_por_jefatura'][0]['nombre'], 'Facturación')
        estados = {item['clave']: item['total'] for item in respuesta.context['estados_acciones']}
        self.assertEqual(estados, {
            'pendiente': 1, 'en_proceso': 1, 'terminado': 0, 'cancelado': 0,
        })
        self.assertContains(respuesta, 'Incidencias · No conformidades')
        self.assertContains(respuesta, 'Estado de actividades por jefatura')
        self.assertContains(respuesta, 'Datos calculados con los registros actuales de la plataforma.')
        self.assertNotContains(respuesta, 'Datos ilustrativos')

    def test_cabecera_muestra_el_area_del_usuario(self):
        self.usuario.area = 'Facturación'
        self.usuario.save(update_fields=['area'])
        self.client.force_login(self.usuario)

        respuesta = self.client.get(reverse('inicio'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, '<div class="user-role">Facturación</div>', html=True)
        self.assertNotContains(respuesta, '<div class="user-role">USUARIO</div>', html=True)

    def test_panel_administrativo_cuenta_como_pendientes_todos_los_hallazgos_abiertos(self):
        borrador = self.crear(titulo='Pendiente en identificación')
        analisis = self.crear(titulo='Pendiente en análisis')
        cerrado = self.crear(titulo='Hallazgo cerrado')
        Hallazgo.objects.filter(pk=analisis.pk).update(estado='EN_ANALISIS')
        Hallazgo.objects.filter(pk=cerrado.pk).update(estado='CERRADO')

        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse('inicio'))

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['resumen']['total'], 3)
        self.assertEqual(respuesta.context['resumen']['pendientes'], 2)
        self.assertEqual(respuesta.context['resumen']['pendientes_validacion'], 0)
        self.assertEqual(respuesta.context['resumen']['en_analisis'], 1)
        self.assertEqual(respuesta.context['resumen']['cerrados'], 1)
        metricas = {item['etiqueta']: item['valor'] for item in respuesta.context['metricas_admin']}
        self.assertEqual(metricas, {
            'Total hallazgos': 3,
            'Pendientes': 2,
            'En análisis': 1,
            'Cerrados': 1,
        })

    def test_post_registro_no_acepta_estado_sac_del_cliente(self):
        d=self.datos();d={k:(v.pk if hasattr(v,'pk') else v) for k,v in d.items()};d.update(aplica_impacto='on',codigo='SAC-FALSO',estado='CERRADO')
        self.client.force_login(self.usuario);r=self.client.post(reverse('hallazgo_crear'),d)
        self.assertEqual(r.status_code,302, getattr(r,'context',None))
        h=Hallazgo.objects.first();self.assertEqual(h.estado,'ACCION_INMEDIATA');self.assertNotEqual(h.codigo,'SAC-FALSO')

    def test_registro_muestra_proceso_antes_y_actividad_opcional(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse('hallazgo_crear'))
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Selecciona un tipo de registro', html)
        self.assertIn('Vista previa automática', html)
        self.assertIn('id="hallazgoCode"', html)
        self.assertIn('readonly', html)
        self.assertNotIn('Guardar borrador', html)
        self.assertIn('Guardar evaluación', html)
        self.assertIn('id="impactoResultadoContenedor"', html)
        self.assertIn('id="impactoIndicador"', html)
        self.assertIn('Impacto calculado:', html)
        self.assertIn("'level-low'", html)
        self.assertIn("'level-medium'", html)
        self.assertIn("'level-high'", html)
        self.assertIn('Clientes afectados', html)
        self.assertIn('Tiempo de afectación', html)
        self.assertIn('Impacto financiero', html)
        self.assertIn('0 – 99 cuentas', html)
        self.assertIn('30 – 120 min', html)
        self.assertIn('S/ 2,000,000 o más', html)
        self.assertEqual(html.count('name="impacto_clientes"'), 3)
        self.assertEqual(html.count('name="impacto_tiempo"'), 3)
        self.assertEqual(html.count('name="impacto_soles"'), 3)
        self.assertIn('Registrar ticket', html)
        self.assertIn('Ej. INC000001305088', html)
        self.assertNotIn('(si aplica)', html)
        self.assertIn('https://clarop-dwp.claro.pe/dwp/app/#/activity', html)
        self.assertIn('target="_blank"', html)
        self.assertIn('¿Es hallazgo tecnológico?', html)
        self.assertIn('name="origen_tecnologico"', html)
        self.assertLess(html.index('Fecha de registro'), html.index('Fecha de detección'))
        self.assertLess(html.index('Fecha de detección'), html.index('Fecha de solución'))
        self.assertLess(html.index('id_proceso'), html.rindex('1. Identificación'))
        self.assertIn('id_actividad', html)
        self.assertNotIn('id_criterio_categoria', html)
        self.assertNotIn('id_requisito_referencia', html)
        self.assertFalse(HallazgoForm(usuario=self.usuario).fields['actividad'].required)
        self.assertEqual(
            list(HallazgoForm(usuario=self.usuario).fields['es_critica'].choices),
            [('', 'Seleccionar'), ('SI', 'Sí - Crítica'), ('NO', 'No - No crítica')],
        )

        formulario_tecnologico = HallazgoForm(data={
            'tipo_registro': TipoRegistro.objects.get(codigo='INC').pk,
            'fuente_deteccion': FuenteDeteccion.objects.get(codigo='OPERACION').pk,
            'proceso': self.proceso.pk,
            'descripcion': 'Incidente tecnológico sin ticket',
            'responsable': self.usuario.pk,
            'fecha_deteccion': timezone.localdate().isoformat(),
            'fecha_solucion': (timezone.localdate() + timedelta(days=1)).isoformat(),
            'impacto_clientes': '1', 'impacto_tiempo': '1', 'impacto_soles': '1',
            'urgencia': Urgencia.objects.get(valor=2).pk,
            'es_critica': 'NO', 'origen_tecnologico': 'True', 'ticket_remedy': '',
        }, usuario=self.usuario)
        self.assertFalse(formulario_tecnologico.is_valid())
        self.assertEqual(
            formulario_tecnologico.errors['ticket_remedy'],
            ['Este campo es obligatorio para hallazgos tecnológicos.'],
        )

        tipo = TipoRegistro.objects.get(codigo='INC')
        preview = CodigoSACService.previsualizar(tipo=tipo)
        invalido = self.client.post(reverse('hallazgo_crear'), {'tipo_registro': tipo.pk})
        self.assertEqual(invalido.status_code, 200)
        self.assertContains(invalido, f'value="{preview}"')
        self.assertFalse(CorrelativoSAC.objects.exists())
        self.assertFalse(Hallazgo.objects.exists())

        intento_borrador = self.client.post(reverse('hallazgo_crear'), {
            'tipo_registro': tipo.pk, 'accion': 'borrador',
        })
        self.assertEqual(intento_borrador.status_code, 200)
        self.assertFalse(Hallazgo.objects.exists())

    def test_administrador_configura_rangos_de_impacto(self):
        from apps.catalogos.models import AuditoriaAdministracion, ConfiguracionImpacto

        self.client.force_login(self.admin)
        url = reverse('configuracion_impacto')
        pantalla = self.client.get(url)
        self.assertEqual(pantalla.status_code, 200)
        self.assertContains(pantalla, 'Configuración de evaluación de impacto')
        self.assertContains(pantalla, 'name="clientes_bajo_hasta"')

        base = {
            'predeterminada': 'on',
            'clientes_bajo_desde': 0, 'clientes_bajo_hasta': 99,
            'clientes_medio_desde': 100, 'clientes_medio_hasta': 499,
            'clientes_alto_desde': 500,
            'tiempo_bajo_desde': 0, 'tiempo_bajo_hasta': 29,
            'tiempo_medio_desde': 30, 'tiempo_medio_hasta': 120,
            'tiempo_alto_desde': 121,
            'financiero_bajo_desde': 0, 'financiero_bajo_hasta': 999999,
            'financiero_medio_desde': 1000000, 'financiero_medio_hasta': 1999999,
            'financiero_alto_desde': 2000000,
        }
        invalido = dict(base, clientes_medio_desde=99)
        respuesta = self.client.post(url, invalido)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no pueden superponerse')

        valido = dict(base, clientes_bajo_hasta=149, clientes_medio_desde=150)
        respuesta = self.client.post(url, valido)
        self.assertEqual(respuesta.status_code, 302)
        configuracion = ConfiguracionImpacto.objects.first()
        self.assertEqual(configuracion.clientes_bajo_hasta, 149)
        self.assertEqual(configuracion.clientes_medio_desde, 150)
        self.assertTrue(AuditoriaAdministracion.objects.filter(
            entidad='ConfiguracionImpacto', objeto=str(configuracion.pk), accion='actualizar',
        ).exists())

    def test_urgencia_por_jefatura_y_configuracion_administrativa(self):
        from apps.catalogos.models import AuditoriaAdministracion

        self.usuario.area = 'Facturación'
        self.usuario.save(update_fields=['area'])
        self.client.force_login(self.usuario)
        pantalla = self.client.get(reverse('hallazgo_crear'))
        self.assertEqual(pantalla.status_code, 200)
        self.assertContains(pantalla, 'Evaluación de urgencia')
        self.assertContains(pantalla, 'Proceso registrado: <b>Facturación</b>', html=True)
        self.assertContains(pantalla, 'Emisión de facturación')
        self.assertContains(pantalla, 'Vencimiento de ciclo')
        self.assertContains(pantalla, 'De 28 a 32 h')

        self.usuario.area = 'Post Facturación'
        self.usuario.save(update_fields=['area'])
        pantalla_post = self.client.get(reverse('hallazgo_crear'))
        self.assertContains(pantalla_post, 'Proceso registrado: <b>Post facturación</b>', html=True)
        self.assertEqual(ConfiguracionUrgencia.codigo_para_area(self.usuario.area), 'POST_FACTURACION')

        self.client.force_login(self.admin)
        url = reverse('configuracion_urgencia')
        self.assertContains(self.client.get(url), 'Configuración de evaluación de urgencia')
        datos = {
            'facturacion-activo': 'on',
            'facturacion-bajo_desde': 0, 'facturacion-bajo_hasta': 29,
            'facturacion-medio_desde': 30, 'facturacion-medio_hasta': 34,
            'facturacion-alto_desde': 35,
            'post_facturacion-activo': 'on',
            'post_facturacion-bajo_desde': 0, 'post_facturacion-bajo_hasta': 27,
            'post_facturacion-medio_desde': 28, 'post_facturacion-medio_hasta': 32,
            'post_facturacion-alto_desde': 33,
        }
        invalido = dict(datos, **{'facturacion-medio_desde': 29})
        respuesta = self.client.post(url, invalido)
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'no pueden superponerse')

        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 302)
        configuracion = ConfiguracionUrgencia.objects.get(codigo='FACTURACION')
        self.assertEqual((configuracion.medio_desde, configuracion.medio_hasta), (30, 34))
        self.assertTrue(AuditoriaAdministracion.objects.filter(
            entidad='ConfiguracionUrgencia', objeto=str(configuracion.pk), accion='actualizar'
        ).exists())

    def test_registro_conserva_rango_de_urgencia_historico(self):
        from apps.hallazgos.registro import RegistroGeneral

        self.usuario.area = 'Facturación'
        self.usuario.save(update_fields=['area'])
        anterior = self.crear(urgencia=Urgencia.objects.get(valor=2))
        self.assertEqual(anterior.urgencia_seleccion, 'De 28 a 32 h')
        self.assertEqual(anterior.urgencia_area, 'Facturación')

        configuracion = ConfiguracionUrgencia.objects.get(codigo='FACTURACION')
        configuracion.bajo_hasta = 29
        configuracion.medio_desde = 30
        configuracion.medio_hasta = 34
        configuracion.alto_desde = 35
        configuracion.save()
        nuevo = self.crear(urgencia=Urgencia.objects.get(valor=2))
        anterior.refresh_from_db()
        self.assertEqual(anterior.urgencia_seleccion, 'De 28 a 32 h')
        self.assertEqual(nuevo.urgencia_seleccion, 'De 30 a 34 h')
        self.assertEqual(RegistroGeneral.objects.get(hallazgo_id=anterior.pk).urgencia, 'De 28 a 32 h')

    def test_registro_general_conserva_los_rangos_de_impacto_historicos(self):
        from apps.catalogos.models import ConfiguracionImpacto
        from apps.hallazgos.registro import RegistroGeneral

        configuracion = ConfiguracionImpacto.objects.get()
        anterior = self.crear(impacto_clientes=3, impacto_tiempo=3, impacto_soles=2)
        self.assertEqual(anterior.impacto_clientes_seleccion, '500 o más cuentas')
        self.assertEqual(anterior.impacto_tiempo_seleccion, '121 o más min')
        self.assertEqual(anterior.impacto_financiero_seleccion, 'S/ 1,000,000 a menos de S/ 2,000,000')

        configuracion.clientes_medio_hasta = 599
        configuracion.clientes_alto_desde = 600
        configuracion.tiempo_medio_hasta = 199
        configuracion.tiempo_alto_desde = 200
        configuracion.financiero_medio_hasta = 2999999
        configuracion.financiero_alto_desde = 3000000
        configuracion.save()

        # Un cambio administrativo no modifica la fotografía de registros anteriores,
        # incluso si después se corrige otro dato de la identificación.
        HallazgoService.actualizar(
            usuario=self.usuario,
            hallazgo=anterior,
            datos={'descripcion': 'Descripción corregida sin reevaluar impacto'},
            version=anterior.version,
        )
        anterior.refresh_from_db()
        self.assertEqual(anterior.impacto_clientes_seleccion, '500 o más cuentas')
        self.assertEqual(anterior.impacto_tiempo_seleccion, '121 o más min')
        self.assertEqual(anterior.impacto_financiero_seleccion, 'S/ 1,000,000 a menos de S/ 2,000,000')

        nuevo = self.crear(impacto_clientes=3, impacto_tiempo=3, impacto_soles=2)
        self.assertEqual(nuevo.impacto_clientes_seleccion, '600 o más cuentas')
        self.assertEqual(nuevo.impacto_tiempo_seleccion, '200 o más min')
        self.assertEqual(nuevo.impacto_financiero_seleccion, 'S/ 1,000,000 a menos de S/ 3,000,000')
        fila = RegistroGeneral.objects.get(hallazgo_id=nuevo.pk)
        self.assertEqual(fila.impacto_clientes_seleccion, '600 o más cuentas')
        self.assertEqual(fila.impacto_tiempo_seleccion, '200 o más min')
        self.assertEqual(fila.impacto_financiero_seleccion, 'S/ 1,000,000 a menos de S/ 3,000,000')

    def test_registro_continua_sin_actividad_ni_referencias_retiradas(self):
        self.client.force_login(self.usuario)
        datos = self.datos()
        post = {
            'tipo_registro': datos['tipo_registro'].pk,
            'fuente_deteccion': datos['fuente_deteccion'].pk,
            'proceso': datos['proceso'].pk,
            'subproceso': '',
            'actividad': '',
            'descripcion': datos['descripcion'],
            'ticket_remedy': '',
            'responsable': datos['responsable'].pk,
            'fecha_deteccion': timezone.localdate().isoformat(),
            'fecha_solucion': datos['fecha_solucion'].isoformat(),
            'impacto_clientes': '1',
            'impacto_tiempo': '2',
            'impacto_soles': '1',
            'urgencia': datos['urgencia'].pk,
            'es_critica': 'NO',
            'accion': 'continuar',
        }
        response = self.client.post(reverse('hallazgo_crear'), post)
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None))
        hallazgo = Hallazgo.objects.get()
        self.assertEqual(hallazgo.estado, 'ACCION_INMEDIATA')
        self.assertEqual(response.url, reverse('hallazgo_accion', args=[hallazgo.pk]))
        self.assertIsNotNone(hallazgo.ciclo_actual)
        self.assertEqual(hallazgo.actividad, '')
        pantalla = self.client.get(reverse('hallazgo_accion', args=[hallazgo.pk]))
        self.assertContains(pantalla, '3. Plan de compromisos')
        self.assertContains(pantalla, 'Agregar compromiso')
        self.assertContains(pantalla, 'Volver a identificación')
        self.assertEqual(timeline_hallazgo(hallazgo)[1]['estado'], 'No aplica')
        plan = {
            'actividades-TOTAL_FORMS': '1', 'actividades-INITIAL_FORMS': '0',
            'actividades-MIN_NUM_FORMS': '1', 'actividades-MAX_NUM_FORMS': '1000',
            'actividades-0-tipo': 'INMEDIATA',
            'actividades-0-descripcion': 'Corregir la desviación detectada',
            'actividades-0-responsable': self.usuario.pk,
            'actividades-0-fet_inicial': timezone.localdate().isoformat(),
            'actividades-0-estado': 'PENDIENTE',
        }
        response = self.client.post(reverse('hallazgo_accion', args=[hallazgo.pk]), plan)
        self.assertEqual(response.url, reverse('hallazgo_acciones_creadas', args=[hallazgo.pk]))
        actividad = hallazgo.ciclo_actual.acciones.get()
        self.assertEqual(actividad.responsable, self.usuario)
        self.assertEqual(actividad.fet_inicial, timezone.localdate())
        confirmacion = self.client.get(reverse('hallazgo_acciones_creadas', args=[hallazgo.pk]))
        self.assertContains(confirmacion, 'Ver seguimiento de actividades')
        self.assertContains(confirmacion, 'Fecha de Compromiso')
        self.assertNotContains(confirmacion, 'FET inicial')
        self.assertContains(confirmacion, 'Eficiencia base')
        seguimiento_pantalla = self.client.get(reverse('hallazgo_acciones_seguimiento', args=[hallazgo.pk]))
        self.assertContains(seguimiento_pantalla, '3 reprogramaciones')
        self.assertContains(seguimiento_pantalla, 'Fecha de Inicio')
        self.assertNotContains(seguimiento_pantalla, 'FET inicial')
        self.assertContains(seguimiento_pantalla, 'Fecha vigente')
        self.assertContains(seguimiento_pantalla, 'Paso 4 bloqueado')
        self.assertContains(seguimiento_pantalla, 'Ver a detalle')
        self.assertContains(seguimiento_pantalla, reverse('hallazgo_detalle', args=[hallazgo.pk]))
        seguimiento = {
            f'accion-{actividad.pk}-estado': 'PENDIENTE',
            f'accion-{actividad.pk}-fecha_real': '',
            'accion': 'guardar',
        }
        response = self.client.post(reverse('hallazgo_acciones_seguimiento', args=[hallazgo.pk]), seguimiento)
        self.assertEqual(response.url, reverse('hallazgo_acciones_seguimiento', args=[hallazgo.pk]))
        hallazgo.refresh_from_db()
        self.assertEqual(hallazgo.estado, 'ACCION_INMEDIATA')
        actividad.refresh_from_db()
        self.assertEqual(actividad.estado, 'PENDIENTE')
        self.assertEqual(self.client.get(reverse('hallazgo_eficacia', args=[hallazgo.pk])).status_code, 403)

        completado = {
            f'accion-{actividad.pk}-estado': 'COMPLETADA',
            f'accion-{actividad.pk}-fecha_real': timezone.localdate().isoformat(),
            'accion': 'evaluar',
        }
        response = self.client.post(reverse('hallazgo_acciones_seguimiento', args=[hallazgo.pk]), completado)
        self.assertEqual(response.url, reverse('hallazgo_eficacia', args=[hallazgo.pk]))
        hallazgo.refresh_from_db()
        actividad.refresh_from_db()
        self.assertEqual(hallazgo.estado, 'EN_VERIFICACION')
        self.assertEqual((actividad.estado, actividad.porcentaje_avance), ('COMPLETADA', 100))
        eficacia = self.client.get(response.url)
        self.assertContains(eficacia, 'Resumen de actividades')
        self.assertContains(eficacia, 'Resultado de eficacia')
        self.assertContains(eficacia, 'Abiertas: <b>0</b>')
        self.assertContains(eficacia, '>Seleccionar</option>')
        response = self.client.post(reverse('hallazgo_eficacia', args=[hallazgo.pk]), {
            'fecha_evaluacion': timezone.localdate().isoformat(), 'resultado': 'EFICAZ',
            'comentario': 'La solución eliminó la desviación.',
        })
        self.assertEqual(response.url, reverse('hallazgo_detalle', args=[hallazgo.pk]))
        self.assertEqual(hallazgo.ciclo_actual.evaluaciones.count(), 1)

    def test_registro_critico_va_directo_a_analisis_sin_validacion(self):
        self.client.force_login(self.usuario)
        datos = self.datos()
        post = {
            'tipo_registro': datos['tipo_registro'].pk,
            'fuente_deteccion': datos['fuente_deteccion'].pk,
            'proceso': datos['proceso'].pk,
            'subproceso': '',
            'actividad': 'Revisión de conciliación',
            'descripcion': datos['descripcion'],
            'ticket_remedy': '',
            'responsable': datos['responsable'].pk,
            'fecha_deteccion': timezone.localdate().isoformat(),
            'fecha_solucion': datos['fecha_solucion'].isoformat(),
            'impacto_clientes': '1',
            'impacto_tiempo': '2',
            'impacto_soles': '1',
            'urgencia': datos['urgencia'].pk,
            'es_critica': 'SI',
            'accion': 'continuar',
        }
        response = self.client.post(reverse('hallazgo_crear'), post)
        hallazgo = Hallazgo.objects.get()
        self.assertEqual(hallazgo.estado, 'EN_ANALISIS')
        self.assertEqual(response.url, reverse('hallazgo_causa', args=[hallazgo.pk]))
        self.assertFalse(hallazgo.historial.filter(accion='VALIDAR').exists())
        self.assertTrue(hallazgo.historial.filter(accion='CONTINUAR_IDENTIFICACION').exists())
        codigo_original = hallazgo.codigo
        causa = self.client.get(reverse('hallazgo_causa', args=[hallazgo.pk]))
        self.assertContains(causa, reverse('hallazgo_editar', args=[hallazgo.pk]))
        identificacion = self.client.get(reverse('hallazgo_editar', args=[hallazgo.pk]))
        self.assertEqual(identificacion.status_code, 200)
        self.assertFalse(identificacion.context['form'].fields['tipo_registro'].disabled)
        tipo_corregido = TipoRegistro.objects.get(codigo='NOC')
        correccion = dict(
            post,
            tipo_registro=tipo_corregido.pk,
            descripcion='Descripción corregida antes del análisis',
            version=hallazgo.version,
        )
        response = self.client.post(reverse('hallazgo_editar', args=[hallazgo.pk]), correccion)
        hallazgo.refresh_from_db()
        self.assertEqual(response.url, reverse('hallazgo_causa', args=[hallazgo.pk]))
        self.assertEqual(hallazgo.estado, 'EN_ANALISIS')
        self.assertNotEqual(hallazgo.codigo, codigo_original)
        self.assertRegex(hallazgo.codigo, r'^SAC-NOC-\d{4}-\d{4}$')
        self.assertEqual(hallazgo.tipo_registro, tipo_corregido)
        cambio = hallazgo.historial.filter(accion='ACTUALIZACION').latest('pk')
        self.assertEqual(cambio.metadata_json['codigo_anterior'], codigo_original)
        self.assertEqual(cambio.metadata_json['codigo_nuevo'], hallazgo.codigo)
        self.assertEqual(hallazgo.descripcion, 'Descripción corregida antes del análisis')
        self.assertEqual(hallazgo.ciclos.count(), 1)

    def test_no_critico_puede_volver_y_cambiar_a_critico_antes_de_crear_actividades(self):
        self.client.force_login(self.usuario)
        datos = self.datos()
        post = {
            'tipo_registro': datos['tipo_registro'].pk, 'fuente_deteccion': datos['fuente_deteccion'].pk,
            'proceso': datos['proceso'].pk, 'subproceso': '', 'actividad': '',
            'descripcion': datos['descripcion'], 'ticket_remedy': '', 'responsable': datos['responsable'].pk,
            'fecha_deteccion': timezone.localdate().isoformat(), 'fecha_solucion': datos['fecha_solucion'].isoformat(),
            'impacto_clientes': '1', 'impacto_tiempo': '2', 'impacto_soles': '1',
            'urgencia': datos['urgencia'].pk, 'es_critica': 'NO', 'accion': 'continuar',
        }
        response = self.client.post(reverse('hallazgo_crear'), post)
        hallazgo = Hallazgo.objects.get()
        self.assertEqual(response.url, reverse('hallazgo_accion', args=[hallazgo.pk]))
        identificacion = self.client.get(reverse('hallazgo_editar', args=[hallazgo.pk]))
        self.assertEqual(identificacion.status_code, 200)
        self.assertFalse(identificacion.context['form'].fields['tipo_registro'].disabled)
        post.update(es_critica='SI', version=hallazgo.version)
        response = self.client.post(reverse('hallazgo_editar', args=[hallazgo.pk]), post)
        hallazgo.refresh_from_db()
        self.assertEqual(hallazgo.estado, 'EN_ANALISIS')
        self.assertEqual(response.url, reverse('hallazgo_causa', args=[hallazgo.pk]))

    def test_semillas_idempotentes(self):
        call_command('seed_initial_data',stdout=StringIO())
        TipoRegistro.objects.filter(codigo='INC').update(valor=None)
        call_command('seed_initial_data',stdout=StringIO())
        self.assertEqual(PreguntaCausa.objects.count(),32);self.assertEqual(MatrizPrioridad.objects.count(),9)
        self.assertEqual({"USUARIO", "VALIDADOR", "ADMINISTRADOR"}, {"USUARIO", "VALIDADOR", "ADMINISTRADOR"})
        from apps.catalogos.models import Catalogo
        tecnicos = Catalogo.objects.filter(clase__in=('TIPO','FUENTE','PRIORIDAD','CATEGORIA'))
        self.assertFalse(tecnicos.filter(valor__isnull=True).exists())
        for clase in ('TIPO','FUENTE','PRIORIDAD','CATEGORIA'):
            valores = list(tecnicos.filter(clase=clase).values_list('valor', flat=True))
            self.assertEqual(len(valores), len(set(valores)))

    def test_catalogo_nuevo_recibe_valor_tecnico_interno(self):
        fuente = FuenteDeteccion.objects.create(codigo='NUEVA', nombre='Fuente nueva')
        self.assertIsNotNone(fuente.valor)
        self.assertNotEqual(
            fuente.valor,
            FuenteDeteccion.objects.get(codigo='OPERACION').valor,
        )

    def test_pantallas_de_tratamiento_y_post_transicion(self):
        h=self.crear(es_critica='SI',origen_tecnologico=True)
        self.client.force_login(self.usuario)
        self.paso(h,'enviar');self.paso(h,'validar',self.calidad);self.paso(h,'iniciar_inmediata')
        for nombre in ['hallazgo_accion','hallazgo_comunicacion','hallazgo_evidencia']:
            self.assertEqual(self.client.get(reverse(nombre,args=[h.pk])).status_code,200)
        a=self.accion(h)
        for nombre in ['accion_seguimiento','accion_reprogramar']:
            self.assertEqual(self.client.get(reverse(nombre,args=[a.pk])).status_code,200)
        self.completar(a)
        ComunicacionService.registrar(usuario=self.usuario,hallazgo=h,datos=dict(destinatarios='Equipo',medio='Reunión',descripcion='Corrección',fecha=timezone.now()))
        self.paso(h,'iniciar_analisis')
        pantalla = self.client.get(reverse('hallazgo_causa',args=[h.pk]))
        self.assertEqual(pantalla.status_code,200)
        self.assertContains(pantalla, 'Despliega una categoría a la vez')
        self.assertContains(pantalla, 'Mano de Obra (Personal)')
        self.assertContains(pantalla, 'name="r_1_1"', count=3)
        self.assertContains(pantalla, '4.1.7')
        self.assertContains(pantalla, 'Completar y habilitar paso 3')
        d={'causa_raiz':'Causa comprobada','finalizar':'1'}
        for p in PreguntaCausa.objects.all(): d['r_'+p.codigo.replace('.','_')]='NO'
        respuesta = self.client.post(reverse('hallazgo_causa',args=[h.pk]),d)
        self.assertEqual(respuesta.status_code,302)
        self.assertEqual(respuesta.url, reverse('hallazgo_pbi', args=[h.pk]))
        h.refresh_from_db()
        self.assertEqual(h.estado, 'PBI_EN_GESTION')
        self.assertEqual(self.client.get(reverse('hallazgo_pbi',args=[h.pk])).status_code,200)
        self.assertEqual(self.client.get(reverse('hallazgo_detalle',args=[h.pk])).status_code,200)

    def test_no_edicion_ajena_http_y_xss(self):
        h=self.crear(titulo='<script>alert(1)</script>');self.client.force_login(self.ajeno)
        for nombre in ['hallazgo_detalle','hallazgo_editar','hallazgo_evidencia']:
            self.assertEqual(self.client.get(reverse(nombre,args=[h.pk])).status_code,404)
        self.client.force_login(self.usuario)
        r=self.client.get(reverse('hallazgo_detalle',args=[h.pk]))
        self.assertNotContains(r,'<script>alert(1)</script>')
        self.assertContains(r,'&lt;script&gt;alert(1)&lt;/script&gt;')

    def test_administracion_catalogo_y_ultimo_admin(self):
        self.client.force_login(self.admin)
        r=self.client.post(reverse('catalogo_crear',args=['procesos']),{'nombre':'Nuevo proceso','activo':'on','validadores':[self.calidad.pk]})
        self.assertEqual(r.status_code,302)
        self.assertTrue(Proceso.objects.get(nombre='Nuevo proceso').validadores.filter(pk=self.calidad.pk).exists())
        r=self.client.post(reverse('usuario_editar',args=[self.admin.pk]),{'roles':['USUARIO'],'is_active':'on'})
        self.assertEqual(r.status_code,200)
        self.assertContains(r,'Debe permanecer al menos un administrador activo.')
        self.admin.refresh_from_db(); self.assertTrue(self.admin.has_role('ADMINISTRADOR'))

    def test_avisos_vencimiento_idempotentes(self):
        h=self.crear();self.paso(h,'enviar');self.paso(h,'validar',self.calidad);self.paso(h,'iniciar_inmediata');self.accion(h)
        call_command('notificar_vencimientos',dias=3,stdout=StringIO())
        call_command('notificar_vencimientos',dias=3,stdout=StringIO())
        self.assertEqual(Notificacion.objects.filter(tipo__startswith='vencimiento_').count(),1)

    def test_catalogo_unificado_separa_tipos_y_conserva_edicion(self):
        from apps.catalogos.models import Catalogo, Prioridad, Impacto
        fuente = FuenteDeteccion.objects.create(codigo='INC', nombre='Fuente con código coincidente')
        self.assertNotEqual(fuente.pk, TipoRegistro.objects.get(codigo='INC').pk)
        self.assertEqual(Catalogo.objects.filter(codigo='INC').count(), 2)
        with self.assertRaises(ValidationError):
            self.crear(urgencia=Urgencia.objects.get(valor=2), fuente_deteccion=FuenteDeteccion(pk=TipoRegistro.objects.get(codigo='INC').pk, clase='TIPO', codigo='INC', nombre='Incorrecto'))
        self.client.force_login(self.admin)
        prioridad = Prioridad.objects.get(codigo='MEDIA')
        response = self.client.post(reverse('catalogo_editar', args=['prioridades', prioridad.pk]), {'codigo': prioridad.codigo, 'nombre': 'Media revisada', 'activo': 'on'})
        self.assertEqual(response.status_code, 302)
        prioridad.refresh_from_db()
        self.assertEqual(prioridad.nombre, 'Media revisada')
        self.assertEqual(prioridad.clase, 'PRIORIDAD')
        self.assertEqual(Impacto.objects.count(), 3)

    def test_registro_general_columnas_multiples_acciones_y_actualizacion(self):
        from apps.hallazgos.registro import RegistroGeneral, COLUMNAS_REGISTRO
        self.proceso.gerencia = 'Gerencia de Operaciones'
        self.proceso.save()
        h = self.crear()
        fila = RegistroGeneral.objects.get(hallazgo_id=h.pk)
        self.assertEqual(fila.gerencia, 'Gerencia de Operaciones')
        self.assertIsNone(fila.accion_id)
        self.assertIsNone(fila.porcentaje_avance)
        self.assertEqual(fila.impacto_clientes_seleccion, '0 – 99 cuentas')
        self.assertEqual(fila.impacto_tiempo_seleccion, '30 – 120 min')
        self.assertEqual(fila.impacto_financiero_seleccion, 'Menos de S/ 1,000,000')
        self.assertEqual(len(COLUMNAS_REGISTRO), 34)
        self.paso(h, 'enviar'); self.paso(h, 'validar', self.calidad); self.paso(h, 'iniciar_inmediata')
        a = self.accion(h); b = self.accion(h)
        self.assertEqual(RegistroGeneral.objects.filter(hallazgo_id=h.pk).count(), 2)
        fila = RegistroGeneral.objects.get(accion_id=a.pk)
        self.assertEqual(fila.porcentaje_avance, 0)
        self.assertEqual(fila.auditor_verificador, str(self.calidad))
        nueva = timezone.localdate() + timedelta(days=5)
        AccionService.reprogramar(usuario=self.usuario, accion=a, nueva_fecha=nueva, motivo='Cambio comprobado')
        fila.refresh_from_db()
        self.assertEqual(fila.fet, nueva)
        self.completar(a)
        fila.refresh_from_db()
        self.assertEqual(fila.estado, 'Terminado')
        self.assertEqual(fila.porcentaje_avance, 100)
        self.assertEqual(a.reprogramaciones.first().metadata_json['fecha_anterior'], str(a.fet_inicial))
        self.assertEqual(a.seguimientos.count(), 1)

    def test_registro_general_permisos_csv_y_cero(self):
        import csv
        from apps.hallazgos.registro import COLUMNAS_REGISTRO
        h = self.crear(descripcion='=SUM(1,2)')
        self.paso(h, 'enviar'); self.paso(h, 'validar', self.calidad); self.paso(h, 'iniciar_inmediata'); self.accion(h)
        url = reverse('registro_general')
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.usuario)
        pagina = self.client.get(url)
        self.assertContains(pagina, h.codigo)
        self.assertContains(pagina, 'data-registro-scroll')
        self.assertContains(pagina, 'Primeras columnas')
        self.assertContains(pagina, 'Últimas columnas')
        self.assertContains(pagina, 'N° Hallazgo')
        rows = list(csv.reader(StringIO(self.client.get(url+'?formato=csv').content.decode('utf-8-sig'))))
        self.assertEqual(rows[0], [titulo for _, titulo in COLUMNAS_REGISTRO])
        self.assertEqual(len(rows[1]), 34)
        self.assertEqual(rows[1][rows[0].index('Clientes afectados · Rango seleccionado')], '0 – 99 cuentas')
        self.assertEqual(rows[1][rows[0].index('Tiempo de afectación · Rango seleccionado')], '30 – 120 min')
        self.assertEqual(rows[1][rows[0].index('Impacto financiero · Rango seleccionado')], 'Menos de S/ 1,000,000')
        self.assertEqual(rows[1][rows[0].index('Porcentaje de Avance')], '0')
        self.assertTrue(rows[1][8].startswith("'="))
        self.client.force_login(self.ajeno)
        self.assertNotContains(self.client.get(url), h.codigo)
        rows = list(csv.reader(StringIO(self.client.get(url+'?formato=csv').content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 1)
        self.assertNotContains(self.client.get(url+'?fecha_desde=invalida'), h.codigo)

    def test_registro_general_cierre_reapertura_y_evidencia(self):
        from apps.hallazgos.registro import RegistroGeneral
        h = self.crear(es_critica='SI'); a = self.inmediata(h); self.analizar(h)
        self.paso(h, 'planificar'); ac = self.accion(h, 'CORRECTIVA'); self.paso(h, 'iniciar_implementacion')
        with TemporaryDirectory() as carpeta, override_settings(MEDIA_ROOT=carpeta):
            EvidenciaService.subir(usuario=self.usuario, hallazgo=h, accion=ac, archivo=SimpleUploadedFile('implementacion.pdf', b'%PDF-1.4\n%%EOF'))
            fila = RegistroGeneral.objects.get(accion_id=ac.pk)
            self.assertIn('implementacion.pdf', fila.evidencia_implementacion)
            self.assertEqual(fila.causas_raiz, 'Falta de control preventivo')
        self.completar(ac); self.verificar(h); self.paso(h, 'cerrar', self.admin)
        fecha = RegistroGeneral.objects.get(accion_id=ac.pk).fecha_cierre
        self.assertIsNotNone(fecha)
        self.paso(h, 'reabrir', self.calidad)
        self.assertEqual(RegistroGeneral.objects.get(accion_id=ac.pk).fecha_cierre, fecha)
        self.assertEqual(RegistroGeneral.objects.filter(hallazgo_id=h.pk).count(), 3)
        self.assertEqual(RegistroGeneral.objects.get(accion_id=ac.pk).resultado_eficacia, 'Eficaz')

    def test_plantillas_oficiales_solo_para_hallazgos_cerrados(self):
        h = self.crear()
        self.client.force_login(self.usuario)
        for tipo in ('solicitud', 'matriz'):
            self.assertEqual(
                self.client.get(reverse('hallazgo_plantilla_descargar', args=[h.pk, tipo])).status_code,
                404,
            )

        self.inmediata(h)
        self.verificar(h)
        self.paso(h, 'cerrar', self.admin)
        pagina = self.client.get(reverse('hallazgo_buscar'))
        self.assertContains(pagina, 'Plantillas')
        self.assertContains(pagina, 'Solicitud AC')
        self.assertContains(pagina, 'Matriz')

        esperados = {
            'solicitud': ('Solicitud_accion_correctiva.xlsx', {'Formato', 'Causa Raiz', 'Control de Cambios'}),
            'matriz': ('Matriz_control_hallazgo.xlsx', {'Hallazgos', 'Hoja1', 'Control de Cambios'}),
        }
        for tipo, (sufijo, hojas) in esperados.items():
            respuesta = self.client.get(reverse('hallazgo_plantilla_descargar', args=[h.pk, tipo]))
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(
                respuesta['Content-Type'],
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            )
            self.assertIn(f'{h.codigo}_{sufijo}', respuesta['Content-Disposition'])
            contenido = b''.join(respuesta.streaming_content)
            with ZipFile(BytesIO(contenido)) as libro:
                nombres = set(libro.namelist())
                self.assertIn('[Content_Types].xml', nombres)
                self.assertTrue(any(nombre.startswith('xl/media/') for nombre in nombres))
                self.assertNotIn('xl/calcChain.xml', nombres)
                if tipo == 'solicitud':
                    self.assertFalse(any(nombre.startswith('xl/externalLinks/') for nombre in nombres))
                workbook = libro.read('xl/workbook.xml').decode('utf-8')
                self.assertNotIn('<externalReferences>', workbook)
                for hoja in hojas:
                    self.assertIn(f'name="{hoja}"', workbook)
                xml_hojas = b'\n'.join(
                    libro.read(nombre) for nombre in nombres if nombre.startswith('xl/worksheets/sheet')
                ).decode('utf-8')
                self.assertIn(h.codigo, xml_hojas)
                self.assertIn('Desviación del procedimiento', xml_hojas)
                self.assertIn('Restablecer condición', xml_hojas)

        self.client.force_login(self.ajeno)
        self.assertEqual(
            self.client.get(reverse('hallazgo_plantilla_descargar', args=[h.pk, 'matriz'])).status_code,
            404,
        )

    def test_tipo_de_plantilla_invalido_no_se_descarga(self):
        h = self.crear()
        self.inmediata(h)
        self.verificar(h)
        self.paso(h, 'cerrar', self.admin)
        self.client.force_login(self.usuario)
        self.assertEqual(
            self.client.get(reverse('hallazgo_plantilla_descargar', args=[h.pk, 'desconocida'])).status_code,
            404,
        )

    def test_analisis_compacto_snapshot_control_y_evidencia(self):
        h=self.crear(es_critica='SI');self.inmediata(h);self.paso(h,'iniciar_analisis')
        control=dict(tipos=['PREVENTIVO'],nombre='Control',descripcion='Validación',mitiga_riesgo='SI',frecuencia='Diaria',responsable='Equipo',evidencia='Documento')
        preguntas = [p for p in PreguntaCausa.objects.all() if p.texto.strip().rstrip(':').casefold() != 'otro']
        respuestas=[dict(pregunta=p,respuesta='SI' if p.pk=='4.1' else 'NO',comentario='Dato original') for p in preguntas]
        ciclo=CausaService.guardar(usuario=self.usuario,hallazgo=h,datos=dict(causa_raiz='Causa',respuestas=respuestas,control=control),finalizar=True)
        self.assertEqual(len(ciclo.respuestas),26)
        self.assertEqual(ciclo.control['nombre'],'Control')
        self.assertEqual(ciclo.analisis_responsable_id,self.usuario.pk)
        with self.assertRaises(ValidationError):
            CausaService.guardar(usuario=self.usuario,hallazgo=h,datos={'causa_raiz':'Sobrescribir'})
        with TemporaryDirectory() as carpeta, override_settings(MEDIA_ROOT=carpeta):
            e=EvidenciaService.subir(usuario=self.usuario,hallazgo=h,analisis=ciclo,archivo=SimpleUploadedFile('analisis.pdf',b'%PDF-1.4\n%%EOF'))
            self.assertEqual(e.analisis_id,ciclo.pk)
        self.client.force_login(self.usuario)
        self.assertContains(self.client.get(reverse('hallazgo_detalle',args=[h.pk])), 'Dato original')

    def test_esquema_productivo_de_24_tablas(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            self.assertEqual(
                {fila[0] for fila in cursor.fetchall()},
                {
                    'tbl_actividad_nc', 'tbl_archivo_evidencia_nc',
                    'tbl_auditoria_administracion_nc', 'tbl_catalogo_nc',
                    'tbl_ciclo_tratamiento_nc', 'tbl_comunicacion_nc',
                    'tbl_configuracion_impacto_nc', 'tbl_configuracion_urgencia_nc',
                    'tbl_correlativo_sac_nc', 'tbl_django_migrations_nc',
                    'tbl_django_session_nc', 'tbl_evaluacion_eficacia_nc',
                    'tbl_evidencia_nc', 'tbl_historial_hallazgo_nc',
                    'tbl_matriz_prioridad_nc', 'tbl_notificacion_nc',
                    'tbl_pbi_nc', 'tbl_pregunta_causa_nc', 'tbl_proceso_nc',
                    'tbl_proceso_validador_nc', 'tbl_registro_general_nc',
                    'tbl_subproceso_nc', 'tbl_usuario_nc', 'tbl_usuario_rol_nc',
                },
            )
            cursor.execute("SELECT count(*) FROM pg_views WHERE schemaname='public'")
            self.assertEqual(cursor.fetchone()[0], 0)


class Concurrencia(TransactionTestCase):
    def setUp(self):
        self.usuario,self.calidad,self.admin,self.ajeno,self.proceso=preparar()

    def test_postgresql_reserva_concurrente_sac(self):
        self.assertEqual(connection.vendor,'postgresql')
        def reservar(_):
            close_old_connections()
            try:
                return CodigoSACService.generar(tipo=TipoRegistro.objects.get(codigo='INC'))
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=4) as pool:
            codigos=list(pool.map(reservar,range(12)))
        self.assertEqual(len(set(codigos)),12)
        self.assertEqual(sorted(int(c.rsplit('-',1)[1]) for c in codigos),list(range(1,13)))

    def test_validacion_simultanea_es_una_sola_transicion(self):
        h=HallazgoService.crear(usuario=self.usuario,datos=dict(titulo='Simultáneo',tipo_registro=TipoRegistro.objects.get(codigo='INC'),fuente_deteccion=FuenteDeteccion.objects.get(codigo='OPERACION'),proceso=self.proceso,responsable=self.usuario,descripcion='Prueba concurrencia',fecha_deteccion=timezone.now(),fecha_solucion=timezone.localdate()+timedelta(days=5),es_critica='NO',aplica_impacto=False,justificacion_no_impacto='Documental',criterio_categoria='No crítica',requisito_referencia='Procedimiento'),borrador=True)
        WorkflowService.ejecutar(usuario=self.usuario,hallazgo=h,accion='enviar')
        def validar(_):
            close_old_connections()
            try:
                WorkflowService.ejecutar(usuario=Usuario.objects.get(pk=self.calidad.pk),hallazgo=Hallazgo.objects.get(pk=h.pk),accion='validar')
                return True
            except ValidationError:
                return False
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados=list(pool.map(validar,range(2)))
        self.assertEqual(sum(resultados),1)
        self.assertEqual(h.historial.filter(accion='VALIDAR').count(),1)
