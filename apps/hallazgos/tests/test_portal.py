from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO, StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.models import Usuario
from apps.catalogos.models import FuenteDeteccion, MatrizPrioridad, PreguntaCausa, Proceso, TipoRegistro, Urgencia
from apps.hallazgos.forms import HallazgoForm
from apps.hallazgos.models import Accion, Hallazgo, HistorialHallazgo, Notificacion
from apps.hallazgos.selectors import hallazgos_visibles, timeline_hallazgo
from apps.hallazgos.services import AccionService, CausaService, ComunicacionService, EficaciaService, EvidenciaService, HallazgoService, PBIService, WorkflowService
from apps.hallazgos.services.hallazgo import CodigoSACService, ImpactoService, PrioridadService


def preparar():
    call_command('seed_initial_data', stdout=StringIO())
    usuarios = []
    for nombre, rol in [('reportante','USUARIO'), ('calidad','VALIDADOR'), ('administrador','ADMINISTRADOR'), ('ajeno','USUARIO')]:
        u = Usuario.objects.create_user(nombre, password='ClaveSoloParaTests-2026!')
        u.groups.add(Group.objects.get(name=rol))
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
        return CausaService.guardar(usuario=self.usuario,hallazgo=h,datos=dict(causa_raiz='Falta de control preventivo',respuestas=[dict(pregunta=p,respuesta='NO',comentario='Revisado') for p in PreguntaCausa.objects.all()],control={}),finalizar=True)

    def verificar(self,h):
        self.paso(h,'enviar_verificacion')
        return EficaciaService.evaluar(usuario=self.calidad,hallazgo=h,datos=dict(fecha_evaluacion=timezone.localdate(),resultado='EFICAZ',comentario='No se repite la desviación'))

    def test_no_critica_recorrido_completo(self):
        h=self.crear(); self.inmediata(h); self.verificar(h); self.paso(h,'cerrar',self.calidad)
        self.assertEqual(h.estado,'CERRADO')
        self.assertEqual(h.ciclos.filter(fecha_cierre__isnull=False).count(),1)
        self.assertEqual(sum(p['estado']=='No aplica' for p in timeline_hallazgo(h)),0)
        with self.assertRaises(ValidationError): self.accion(h)

    def test_critica_tecnologica_exige_6m_pbi_y_correctivas(self):
        h=self.crear(es_critica='SI',origen_tecnologico=True); self.inmediata(h)
        with self.assertRaises(ValidationError): self.paso(h,'enviar_verificacion')
        self.analizar(h)
        with self.assertRaises(ValidationError): self.paso(h,'planificar')
        self.paso(h,'iniciar_pbi')
        with self.assertRaises(ValidationError): self.paso(h,'planificar')
        PBIService.guardar(usuario=self.usuario,hallazgo=h,datos=dict(numero_pbi='PBI-TEST',sistema='Facturación',responsable_ti=self.usuario,estado='ABIERTO',fecha_cierre=None))
        self.paso(h,'planificar'); a=self.accion(h,'CORRECTIVA'); self.paso(h,'iniciar_implementacion'); self.completar(a)
        self.verificar(h);self.paso(h,'cerrar',self.calidad)
        self.assertEqual(h.estado,'CERRADO')
        self.assertEqual(len(h.ciclo_actual.respuestas),32)

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
        self.verificar(h);self.paso(h,'cerrar',self.calidad)
        self.assertEqual(h.ciclos.first().evaluaciones.first().resultado,'NO_EFICAZ')

    def test_reapertura_manual_no_borra_cierre(self):
        h=self.crear();self.inmediata(h);self.verificar(h);self.paso(h,'cerrar',self.calidad);self.paso(h,'reabrir',self.calidad)
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
        self.usuario.groups.add(Group.objects.get(name='VALIDADOR'));self.proceso.validadores.add(self.usuario)
        self.usuario=Usuario.objects.get(pk=self.usuario.pk)
        h=self.crear();self.paso(h,'enviar')
        with self.assertRaises(PermissionDenied): self.paso(h,'validar',self.usuario)

    def test_sac_unico_y_tipo_inmutable(self):
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

    def test_no_saltos_ni_cierre_sin_eficacia_comunicacion(self):
        h=self.crear()
        with self.assertRaises(ValidationError): self.paso(h,'cerrar',self.calidad)
        self.paso(h,'enviar');self.paso(h,'validar',self.calidad);self.paso(h,'iniciar_inmediata');self.completar(self.accion(h))
        with self.assertRaises(ValidationError): self.paso(h,'enviar_verificacion')
        ComunicacionService.registrar(usuario=self.usuario,hallazgo=h,datos=dict(destinatarios='Equipo',medio='Reunión',descripcion='Corrección',fecha=timezone.now()))
        self.paso(h,'enviar_verificacion')
        with self.assertRaises(ValidationError): self.paso(h,'cerrar',self.calidad)

    def test_control_6m_obligatorio_y_snapshot(self):
        h=self.crear(es_critica='SI');self.inmediata(h);self.paso(h,'iniciar_analisis')
        respuestas=[dict(pregunta=p,respuesta='SI' if p.pk=='4.1' else 'NO',comentario='') for p in PreguntaCausa.objects.all()]
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
        self.client.force_login(self.calidad);self.assertEqual(self.client.get(reverse('usuarios')).status_code,403)
        self.client.force_login(self.admin)
        for url in ['/',reverse('usuarios'),reverse('catalogos'),reverse('auditoria'),reverse('reportes'),reverse('usuario_crear'),reverse('catalogo_crear',args=['procesos'])]:
            self.assertEqual(self.client.get(url).status_code,200,url)
        self.assertEqual(self.client.get(reverse('hallazgo_crear')).status_code,403)
        seguro=Client(enforce_csrf_checks=True);seguro.force_login(self.usuario)
        self.assertEqual(seguro.post(reverse('hallazgo_crear'),{}).status_code,403)
        self.assertEqual(self.client.get(reverse('logout')).status_code,405)

    def test_post_registro_no_acepta_estado_sac_del_cliente(self):
        d=self.datos();d={k:(v.pk if hasattr(v,'pk') else v) for k,v in d.items()};d.update(aplica_impacto='on',codigo='SAC-FALSO',estado='CERRADO')
        self.client.force_login(self.usuario);r=self.client.post(reverse('hallazgo_crear'),d)
        self.assertEqual(r.status_code,302, getattr(r,'context',None))
        h=Hallazgo.objects.first();self.assertEqual(h.estado,'BORRADOR');self.assertNotEqual(h.codigo,'SAC-FALSO')

    def test_registro_muestra_proceso_antes_y_actividad_opcional(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse('hallazgo_crear'))
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Se generará automáticamente', html)
        self.assertIn('Guardar evaluación', html)
        self.assertLess(html.index('id_proceso'), html.rindex('1. Identificación'))
        self.assertIn('id_actividad', html)
        self.assertNotIn('id_criterio_categoria', html)
        self.assertNotIn('id_requisito_referencia', html)
        self.assertFalse(HallazgoForm(usuario=self.usuario).fields['actividad'].required)

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
        self.assertEqual(hallazgo.estado, 'EN_ANALISIS')
        self.assertEqual(response.url, reverse('hallazgo_causa', args=[hallazgo.pk]))
        self.assertIsNotNone(hallazgo.ciclo_actual)
        self.assertEqual(hallazgo.actividad, '')
        checklist = {'finalizar': '1'}
        for pregunta in PreguntaCausa.objects.all():
            checklist['r_' + pregunta.codigo.replace('.', '_')] = 'NO'
        response = self.client.post(reverse('hallazgo_causa', args=[hallazgo.pk]), checklist)
        hallazgo.refresh_from_db()
        self.assertEqual(response.url, reverse('hallazgo_accion', args=[hallazgo.pk]))
        self.assertEqual(hallazgo.estado, 'ACCION_INMEDIATA')

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

    def test_semillas_idempotentes(self):
        call_command('seed_initial_data',stdout=StringIO());call_command('seed_initial_data',stdout=StringIO())
        self.assertEqual(PreguntaCausa.objects.count(),32);self.assertEqual(MatrizPrioridad.objects.count(),9)
        self.assertEqual(Group.objects.count(),3)

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
        r=self.client.post(reverse('usuario_editar',args=[self.admin.pk]),{'roles':[Group.objects.get(name='USUARIO').pk],'is_active':'on'})
        self.assertEqual(r.status_code,200)
        self.assertContains(r,'Debe permanecer al menos un administrador activo.')
        self.assertTrue(self.admin.groups.filter(name='ADMINISTRADOR').exists())

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
        self.assertEqual(len(COLUMNAS_REGISTRO), 31)
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
        self.assertEqual(fila.estado, 'Completada')
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
        self.assertContains(self.client.get(url), h.codigo)
        rows = list(csv.reader(StringIO(self.client.get(url+'?formato=csv').content.decode('utf-8-sig'))))
        self.assertEqual(rows[0], [titulo for _, titulo in COLUMNAS_REGISTRO])
        self.assertEqual(len(rows[1]), 31)
        self.assertEqual(rows[1][24], '0')
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
        self.completar(ac); self.verificar(h); self.paso(h, 'cerrar', self.calidad)
        fecha = RegistroGeneral.objects.get(accion_id=ac.pk).fecha_cierre
        self.assertIsNotNone(fecha)
        self.paso(h, 'reabrir', self.calidad)
        self.assertEqual(RegistroGeneral.objects.get(accion_id=ac.pk).fecha_cierre, fecha)
        self.assertEqual(RegistroGeneral.objects.filter(hallazgo_id=h.pk).count(), 3)
        self.assertEqual(RegistroGeneral.objects.get(accion_id=ac.pk).resultado_eficacia, 'Eficaz')

    def test_analisis_compacto_snapshot_control_y_evidencia(self):
        h=self.crear(es_critica='SI');self.inmediata(h);self.paso(h,'iniciar_analisis')
        control=dict(tipos=['PREVENTIVO'],nombre='Control',descripcion='Validación',mitiga_riesgo='SI',frecuencia='Diaria',responsable='Equipo',evidencia='Documento')
        respuestas=[dict(pregunta=p,respuesta='SI' if p.pk=='4.1' else 'NO',comentario='Dato original') for p in PreguntaCausa.objects.all()]
        ciclo=CausaService.guardar(usuario=self.usuario,hallazgo=h,datos=dict(causa_raiz='Causa',respuestas=respuestas,control=control),finalizar=True)
        self.assertEqual(len(ciclo.respuestas),32)
        self.assertEqual(ciclo.control['nombre'],'Control')
        self.assertEqual(ciclo.analisis_responsable_id,self.usuario.pk)
        with self.assertRaises(ValidationError):
            CausaService.guardar(usuario=self.usuario,hallazgo=h,datos={'causa_raiz':'Sobrescribir'})
        with TemporaryDirectory() as carpeta, override_settings(MEDIA_ROOT=carpeta):
            e=EvidenciaService.subir(usuario=self.usuario,hallazgo=h,analisis=ciclo,archivo=SimpleUploadedFile('analisis.pdf',b'%PDF-1.4\n%%EOF'))
            self.assertEqual(e.analisis_id,ciclo.pk)
        self.client.force_login(self.usuario)
        self.assertContains(self.client.get(reverse('hallazgo_detalle',args=[h.pk])), 'Dato original')

    def test_reduccion_fisica_de_tablas(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
            self.assertLessEqual(cursor.fetchone()[0], 10)
            cursor.execute("SELECT count(*) FROM pg_views WHERE schemaname='public' AND viewname='registro_general'")
            self.assertEqual(cursor.fetchone()[0], 1)


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
