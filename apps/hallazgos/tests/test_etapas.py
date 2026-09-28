from django.template.loader import render_to_string
from django.test import SimpleTestCase
from apps.hallazgos.models import Hallazgo
from apps.hallazgos.selectors import timeline_hallazgo


class EtapasPrototipo(SimpleTestCase):
    def test_identificacion_respeta_los_cuatro_pasos_aprobados(self):
        pasos = timeline_hallazgo(Hallazgo(estado='BORRADOR'))
        self.assertEqual([p['etiqueta'] for p in pasos], [
            'Identificación', 'Análisis de causa raíz', 'Solución inmediata', 'Evaluación de eficacia',
        ])
        self.assertEqual([p['bloqueado'] for p in pasos], [False, False, True, True])
        html = render_to_string('includes/stepper.html', {'timeline': pasos})
        self.assertEqual(html.count('class="bubble"'), 4)
        self.assertEqual(html.count('aria-current="step"'), 1)
        self.assertIn('3. Solución inmediata<br>y acciones correctivas', html)
        self.assertIn('4. Evaluación de eficacia<br>y cierre', html)
        self.assertNotIn('Validación', html)

    def test_el_paso_tres_muestra_el_analisis_completado(self):
        pasos = timeline_hallazgo(Hallazgo(estado='ACCION_INMEDIATA', es_critica='SI'))
        self.assertEqual(pasos[1]['estado'], 'Completado')
        self.assertEqual(pasos[2]['estado'], 'Actual')
        pasos = timeline_hallazgo(Hallazgo(estado='EN_ANALISIS', es_critica='SI'))
        self.assertEqual(pasos[1]['estado'], 'Actual')
        self.assertEqual(pasos[2]['estado'], 'Pendiente')

    def test_no_critico_marca_analisis_como_no_aplica(self):
        pasos = timeline_hallazgo(Hallazgo(estado='ACCION_INMEDIATA', es_critica='NO'))
        self.assertEqual([p['estado'] for p in pasos], ['Completado', 'No aplica', 'Actual', 'Pendiente'])
        pasos = timeline_hallazgo(Hallazgo(estado='CERRADO', es_critica='NO'))
        self.assertEqual([p['estado'] for p in pasos], ['Completado', 'No aplica', 'Completado', 'Completado'])
