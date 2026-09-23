"""Ensaya la migración sobre datos históricos en una base temporal, nunca en la real."""
import os
import sys
from pathlib import Path
from uuid import uuid4

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
import psycopg
from psycopg import sql
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


def main():
    original = settings.DATABASES['default'].copy()
    temporal = 'test_nc_migracion_' + uuid4().hex[:10]
    admin = dict(host=original['HOST'], port=original['PORT'], user=original['USER'], password=original['PASSWORD'], dbname='postgres', autocommit=True)
    with psycopg.connect(**admin) as c:
        c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(temporal)))
    try:
        connection.close()
        connection.settings_dict['NAME'] = temporal
        assert connection.settings_dict['NAME'].startswith('test_nc_migracion_')
        executor = MigrationExecutor(connection)
        inicial = [('hallazgos', '0001_initial')]
        executor.migrate(inicial)
        old = executor.loader.project_state(inicial).apps
        def obj(app, name, **values):
            return old.get_model(app, name).objects.create(**values)
        ahora = timezone.now()
        u = obj('accounts', 'Usuario', username='historico', password='hash-que-debe-conservarse', first_name='Ana', last_name='Prueba')
        tipo = obj('catalogos', 'TipoRegistro', codigo='INC', nombre='Incidente')
        fuente = obj('catalogos', 'FuenteDeteccion', codigo='OPERACION', nombre='Operación')
        impacto = obj('catalogos', 'Impacto', valor=2, nombre='Medio')
        urgencia = obj('catalogos', 'Urgencia', valor=3, nombre='Alta')
        prioridad = obj('catalogos', 'Prioridad', codigo='ALTA', nombre='Alta')
        matriz = obj('catalogos', 'MatrizPrioridad', impacto=impacto, urgencia=urgencia, prioridad=prioridad)
        estado = obj('catalogos', 'EstadoHallazgo', codigo='REABIERTO', nombre='Reabierto', orden=12)
        proceso = obj('catalogos', 'Proceso', nombre='Proceso histórico', responsable=u)
        proceso.validadores.add(u)
        sub = obj('catalogos', 'Subproceso', proceso=proceso, nombre='Subproceso histórico')
        categoria = obj('catalogos', 'CategoriaCausa', codigo='1', nombre='Método', orden=1)
        pregunta = obj('catalogos', 'PreguntaCausa', codigo='1.1', categoria=categoria, texto='Pregunta original', orden=1)
        h = obj('hallazgos', 'Hallazgo', codigo='SAC-INC-2026-0001', titulo='Historia completa', descripcion='Conservar', tipo_registro=tipo, fuente_deteccion=fuente, proceso=proceso, subproceso=sub, responsable=u, registrado_por=u, updated_by=u, estado=estado, urgencia=urgencia, prioridad=prioridad, prioridad_snapshot='Alta', impacto_resultante=2, es_critica='SI')
        obj('hallazgos', 'CorrelativoSAC', anio=2026, ambito='INC', ultimo_numero=1)
        c1 = obj('hallazgos', 'CicloTratamiento', hallazgo=h, numero=1, motivo='Inicial', creado_por=u, fecha_fin=ahora)
        c2 = obj('hallazgos', 'CicloTratamiento', hallazgo=h, numero=2, motivo='Reabierto', creado_por=u)
        analisis = obj('hallazgos', 'AnalisisCausa', id=81, ciclo=c1, responsable=u, causa_raiz='Causa histórica', fecha_finalizacion=ahora, checklist_snapshot=[{'id': '1.1', 'codigo': '1.1', 'texto': 'Pregunta original'}])
        obj('hallazgos', 'RespuestaCausa', analisis=analisis, pregunta=pregunta, codigo_snapshot='1.1', texto_snapshot='Texto histórico', respuesta='SI', comentario='Respuesta conservada', usuario=u)
        obj('hallazgos', 'ControlProceso', analisis=analisis, tipos=['PREVENTIVO'], nombre='Control', descripcion='Descripción del control', mitiga_riesgo='SI', frecuencia='Diaria', responsable='Ana', evidencia='Referencia')
        a = obj('hallazgos', 'Accion', ciclo=c1, codigo=h.codigo+'-A01', tipo='CORRECTIVA', descripcion='Acción histórica', responsable=u, fecha_inicio=ahora.date(), fet_inicial=ahora.date(), fecha_vigente=ahora.date(), resultado_esperado='Resultado', estado='COMPLETADA', porcentaje_avance=100, fecha_real=ahora.date())
        obj('hallazgos', 'SeguimientoAccion', accion=a, estado='COMPLETADA', porcentaje_avance=100, comentario='Seguimiento original', usuario=u)
        obj('hallazgos', 'ReprogramacionAccion', accion=a, numero_reprogramacion=1, fecha_anterior=ahora.date(), nueva_fecha=ahora.date(), motivo='Motivo original', usuario=u)
        evaluacion = obj('hallazgos', 'EvaluacionEficacia', ciclo=c1, evaluador=u, fecha_evaluacion=ahora.date(), resultado='EFICAZ', comentario='Evaluación original')
        cierre = obj('hallazgos', 'CierreHallazgo', id=93, ciclo=c1, hallazgo=h, responsable_cierre=u, observaciones='Cierre original', resultado='EFICAZ')
        obj('hallazgos', 'ComunicacionHallazgo', ciclo=c1, registrado_por=u, destinatarios='Equipo', medio='Reunión', descripcion='Comunicación original')
        obj('hallazgos', 'PBI', ciclo=c1, numero_pbi='PBI-HIST', sistema='Sistema', responsable_ti=u)
        for campo, contexto in [('analisis', analisis), ('cierre', cierre), ('evaluacion', evaluacion), ('accion', a)]:
            obj('hallazgos', 'Evidencia', hallazgo=h, archivo='evidencias/1/'+campo+'.pdf', nombre_original=campo+'.pdf', mime_type='application/pdf', tamanio=20, subido_por=u, **{campo: contexto})
        obj('hallazgos', 'HistorialHallazgo', hallazgo=h, usuario=u, accion='CREACION', comentario='Historial original')
        obj('hallazgos', 'Notificacion', usuario=u, hallazgo=h, tipo='prueba', titulo='Aviso original', mensaje='Mensaje')
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        from apps.accounts.models import Usuario
        from apps.catalogos.models import MatrizPrioridad, PreguntaCausa, Proceso
        from apps.hallazgos.models import Hallazgo, CicloTratamiento, Accion, Evidencia, HistorialHallazgo, CorrelativoSAC
        from apps.hallazgos.registro import RegistroGeneral
        nuevo = Hallazgo.objects.get(pk=h.pk)
        assert nuevo.codigo == h.codigo and nuevo.estado == 'REABIERTO'
        assert nuevo.tipo_registro.codigo == 'INC' and nuevo.fuente_deteccion.codigo == 'OPERACION'
        assert nuevo.urgencia.valor == 3 and nuevo.prioridad.codigo == 'ALTA'
        assert Usuario.objects.get(pk=u.pk).password == u.password
        assert Proceso.objects.get(pk=proceso.pk).validadores.count() == 1
        assert MatrizPrioridad.objects.get(pk=matriz.pk).impacto.valor == 2
        assert PreguntaCausa.objects.get(pk='1.1').categoria.codigo == '1'
        ciclo = CicloTratamiento.objects.get(pk=c1.pk)
        assert ciclo.causa_raiz == 'Causa histórica' and ciclo.analisis_responsable_id == u.pk
        assert ciclo.respuestas[0]['texto_snapshot'] == 'Texto histórico'
        assert ciclo.respuestas[0]['usuario_id'] == u.pk
        assert ciclo.control['evidencia'] == 'Referencia'
        assert ciclo.comentarios_cierre == 'Cierre original' and ciclo.fecha_cierre == cierre.fecha_cierre
        assert CicloTratamiento.objects.get(pk=c2.pk).fecha_cierre is None
        assert nuevo.ciclos.count() == 2 and ciclo.pbis.count() == 1 and ciclo.comunicaciones.count() == 1
        accion = Accion.objects.get(pk=a.pk)
        assert accion.reprogramaciones.count() == 1 and accion.seguimientos.count() == 1
        assert accion.reprogramaciones.first().metadata_json['fecha_anterior'] == str(ahora.date())
        assert accion.seguimientos.first().comentario == 'Seguimiento original'
        assert HistorialHallazgo.objects.filter(comentario='Historial original').exists()
        assert Evidencia.objects.get(nombre_original='analisis.pdf').analisis_id == c1.pk
        assert Evidencia.objects.get(nombre_original='cierre.pdf').cierre_id == c1.pk
        assert Evidencia.objects.get(nombre_original='accion.pdf').accion_id == a.pk
        assert Evidencia.objects.get(nombre_original='evaluacion.pdf').evaluacion_id == evaluacion.pk
        assert Evidencia.objects.count() == 4
        assert CorrelativoSAC.objects.get(anio=2026, ambito='INC').ultimo_numero == 1
        assert RegistroGeneral.objects.filter(hallazgo_id=h.pk).count() == 2
        fila = RegistroGeneral.objects.get(accion_id=a.pk)
        assert fila.resultado_eficacia == 'Eficaz' and fila.causas_raiz == 'Causa histórica'
        assert fila.evidencia_implementacion == 'accion.pdf'
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'")
            assert cursor.fetchone()[0] == 10
        print('OK: migración 39 → 10; usuarios, catálogos, ciclos, 6M, control, cierre, historial, correlativo, PBI, comunicaciones y evidencias conservados.')
    finally:
        connection.close()
        connection.settings_dict['NAME'] = original['NAME']
        with psycopg.connect(**admin) as c:
            c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(temporal)))


if __name__ == '__main__':
    main()
