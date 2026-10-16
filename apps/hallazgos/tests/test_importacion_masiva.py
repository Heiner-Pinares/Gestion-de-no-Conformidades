from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.catalogos.models import Catalogo, Proceso
from apps.hallazgos.importacion_masiva import ErrorCargaMasiva, ImportadorMasivo, _leer_xlsx
from apps.hallazgos.models import Accion, EvaluacionEficacia, Hallazgo, HistorialHallazgo


class ImportacionMasivaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user("admin.carga", password="Clave-de-prueba-2026!", roles=["ADMINISTRADOR"])
        cls.usuario = Usuario.objects.create_user("responsable.carga", password="Clave-de-prueba-2026!", roles=["USUARIO"], area="Facturación")
        cls.calidad = Usuario.objects.create_user("calidad.carga", password="Clave-de-prueba-2026!", roles=["VALIDADOR"])
        cls.tipo = Catalogo.objects.create(clase="TIPO", codigo="NOC", nombre="No conforme", orden=1)
        cls.proceso = Proceso.objects.create(nombre="Facturacion", gerencia="Operaciones Comerciales", responsable=cls.usuario)

    def hojas(self):
        ahora = timezone.now().replace(microsecond=0)
        hoy = timezone.localdate()
        return {
            "Hallazgos": [
                {"__fila__": 2, "hallazgo_codigo": "SAC-NOC-2025-0100", "titulo": "Pendiente histórico", "tipo_codigo": "NOC", "proceso": "Facturacion", "responsable_usuario": self.usuario.username, "registrado_por_usuario": self.usuario.username, "fecha_registro": ahora.isoformat(), "estado": "BORRADOR", "aplica_impacto": "NO", "justificacion_no_impacto": "Pendiente de evaluación"},
                {"__fila__": 3, "hallazgo_codigo": "SAC-NOC-2025-0101", "titulo": "Cerrado histórico", "tipo_codigo": "NOC", "proceso": "Facturacion", "responsable_usuario": self.usuario.username, "registrado_por_usuario": self.usuario.username, "fecha_registro": (ahora - timedelta(days=40)).isoformat(), "estado": "CERRADO", "aplica_impacto": "NO", "justificacion_no_impacto": "Migración histórica", "es_critica": "NO"},
            ],
            "Ciclos": [{"__fila__": 2, "hallazgo_codigo": "SAC-NOC-2025-0101", "ciclo_numero": 1, "motivo": "Tratamiento inicial", "creado_por_usuario": self.usuario.username, "fecha_inicio": (ahora - timedelta(days=35)).isoformat(), "fecha_fin": (ahora - timedelta(days=1)).isoformat(), "cierre_responsable_usuario": self.admin.username, "fecha_cierre": (ahora - timedelta(days=1)).isoformat(), "comentarios_cierre": "Expediente conforme", "resultado_cierre": "EFICAZ"}],
            "Respuestas_6M": [],
            "Compromisos": [{"__fila__": 2, "hallazgo_codigo": "SAC-NOC-2025-0101", "ciclo_numero": 1, "accion_codigo": "SAC-NOC-2025-0101-A01", "tipo": "INMEDIATA", "descripcion": "Corregir el registro", "responsable_usuario": self.usuario.username, "fecha_inicio": hoy - timedelta(days=30), "fet_inicial": hoy - timedelta(days=20), "fecha_vigente": hoy - timedelta(days=20), "fecha_real": hoy - timedelta(days=21), "estado": "COMPLETADA", "porcentaje_avance": 100, "resultado_esperado": "Registro corregido", "comentario": "Terminado"}],
            "Seguimientos": [{"__fila__": 2, "accion_codigo": "SAC-NOC-2025-0101-A01", "seguimiento_numero": 1, "usuario": self.usuario.username, "fecha_hora": (ahora - timedelta(days=21)).isoformat(), "estado": "COMPLETADA", "porcentaje_avance": 100, "fecha_real": hoy - timedelta(days=21), "comentario": "Se completó el compromiso"}],
            "Reprogramaciones": [],
            "Evaluaciones": [{"__fila__": 2, "hallazgo_codigo": "SAC-NOC-2025-0101", "ciclo_numero": 1, "evaluacion_numero": 1, "evaluador_usuario": self.calidad.username, "fecha_evaluacion": hoy - timedelta(days=2), "resultado": "EFICAZ", "comentario": "No se repitió el hallazgo", "fecha_registro": (ahora - timedelta(days=2)).isoformat()}],
            "Comunicaciones": [], "PBI": [], "Evidencias": [],
        }

    def test_importa_hallazgos_en_curso_y_cerrados_con_relaciones(self):
        resumen = ImportadorMasivo(hojas=self.hojas(), ejecutado_por=self.admin).preparar().guardar()
        self.assertEqual(resumen["hallazgos"], 2)
        self.assertEqual(Hallazgo.objects.get(codigo="SAC-NOC-2025-0100").estado, "BORRADOR")
        cerrado = Hallazgo.objects.get(codigo="SAC-NOC-2025-0101")
        self.assertEqual(cerrado.estado, "CERRADO")
        self.assertEqual(cerrado.ciclos.count(), 1)
        self.assertEqual(Accion.objects.get(codigo="SAC-NOC-2025-0101-A01").porcentaje_avance, 100)
        self.assertEqual(EvaluacionEficacia.objects.get(ciclo__hallazgo=cerrado).resultado, "EFICAZ")
        self.assertTrue(HistorialHallazgo.objects.filter(hallazgo=cerrado, accion="IMPORTACION_MASIVA").exists())

    def test_rechaza_lote_completo_si_un_codigo_ya_existe(self):
        ImportadorMasivo(hojas=self.hojas(), ejecutado_por=self.admin).preparar().guardar()
        with self.assertRaises(ErrorCargaMasiva):
            ImportadorMasivo(hojas=self.hojas(), ejecutado_por=self.admin).preparar()
        self.assertEqual(Hallazgo.objects.count(), 2)

    def test_revierte_todo_si_la_base_rechaza_un_registro_relacionado(self):
        importador = ImportadorMasivo(hojas=self.hojas(), ejecutado_por=self.admin).preparar()
        with patch("apps.hallazgos.importacion_masiva.Accion.save", side_effect=IntegrityError("fallo controlado")):
            with self.assertRaises(IntegrityError):
                importador.guardar()
        self.assertEqual(Hallazgo.objects.count(), 0)

    def test_administrador_descarga_plantilla_y_el_libro_tiene_las_hojas(self):
        self.client.force_login(self.admin)
        respuesta = self.client.get(reverse("hallazgo_carga_masiva_plantilla"))
        self.assertEqual(respuesta.status_code, 200)
        contenido = b"".join(respuesta.streaming_content)
        self.assertTrue(contenido.startswith(b"PK"))
        hojas = _leer_xlsx(contenido)
        self.assertEqual(set(hojas), {"Carga masiva"})

    def test_importa_plantilla_de_una_sola_hoja(self):
        ahora = timezone.now().replace(microsecond=0)
        hoy = timezone.localdate()
        hojas = {
            "Carga masiva": [{
                "__fila__": 2,
                "Código hallazgo *": "SAC-NOC-2025-0200",
                "Título *": "Hallazgo cerrado desde hoja única",
                "Tipo (código) *": "NOC",
                "Proceso *": "Facturacion",
                "Responsable hallazgo *": self.usuario.username,
                "Fecha registro *": (ahora - timedelta(days=30)).isoformat(),
                "Estado hallazgo *": "CERRADO",
                "Aplica impacto *": "NO",
                "Justificación sin impacto": "Expediente histórico",
                "Es crítica": "NO",
                "Código compromiso": "SAC-NOC-2025-0200-A01",
                "Tipo compromiso": "INMEDIATA",
                "Descripción compromiso": "Corregir el registro",
                "Responsable compromiso": self.usuario.username,
                "Inicio compromiso": hoy - timedelta(days=25),
                "Fecha límite original": hoy - timedelta(days=10),
                "Fecha límite vigente": hoy - timedelta(days=10),
                "Estado compromiso": "COMPLETADA",
                "Avance %": 100,
                "Fecha real": hoy - timedelta(days=11),
                "Resultado esperado": "Registro corregido",
                "Comentario compromiso": "Completado",
                "Resultado eficacia": "EFICAZ",
                "Evaluador": self.calidad.username,
                "Fecha evaluación": hoy - timedelta(days=2),
                "Comentario evaluación": "Resultado conforme",
                "Fecha cierre": ahora - timedelta(days=1),
                "Responsable cierre": self.calidad.username,
                "Comentario cierre": "Cierre conforme",
            }]
        }
        resumen = ImportadorMasivo(hojas=hojas, ejecutado_por=self.admin).preparar().guardar()
        self.assertEqual(resumen["hallazgos"], 1)
        hallazgo = Hallazgo.objects.get(codigo="SAC-NOC-2025-0200")
        self.assertEqual(hallazgo.estado, "CERRADO")
        self.assertEqual(hallazgo.ciclos.get().acciones.get().porcentaje_avance, 100)
        self.assertEqual(hallazgo.ciclos.get().evaluaciones.get().resultado, "EFICAZ")
