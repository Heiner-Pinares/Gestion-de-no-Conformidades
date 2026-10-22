from datetime import timedelta
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Usuario
from apps.catalogos.models import Catalogo, Proceso
from apps.hallazgos.importacion_masiva import ErrorCargaMasiva, ImportadorMasivo, _leer_xlsx
from apps.hallazgos.models import Accion, CorrelativoSAC, EvaluacionEficacia, Hallazgo, HistorialHallazgo


class ImportacionMasivaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user("admin.carga", password="Clave-de-prueba-2026!", roles=["ADMINISTRADOR"], first_name="Juan Carlos", last_name="Tello")
        cls.usuario = Usuario.objects.create_user("responsable.carga", password="Clave-de-prueba-2026!", roles=["USUARIO"], area="Facturación", first_name="Walter", last_name="Ramírez")
        cls.calidad = Usuario.objects.create_user("calidad.carga", password="Clave-de-prueba-2026!", roles=["VALIDADOR"])
        cls.tipo = Catalogo.objects.create(clase="TIPO", codigo="NOC", nombre="No conforme", orden=1)
        cls.fuente = Catalogo.objects.create(clase="FUENTE", codigo="AUDITORIA", nombre="Hallazgo de auditoría", orden=1)
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
                "Tipo compromiso": "INMEDIATA",
                "Descripción compromiso": "Corregir el registro",
                "Fecha límite compromiso": hoy - timedelta(days=10),
                "Estado compromiso": "COMPLETADA",
                "Fecha real": hoy - timedelta(days=11),
                "Evaluador cierre": self.calidad.username,
                "Fecha evaluación": hoy - timedelta(days=2),
                "Fecha cierre": ahora - timedelta(days=1),
            }]
        }
        resumen = ImportadorMasivo(hojas=hojas, ejecutado_por=self.admin).preparar().guardar()
        self.assertEqual(resumen["hallazgos"], 1)
        hallazgo = Hallazgo.objects.get()
        self.assertRegex(hallazgo.codigo, rf"^SAC-NOC-{ahora.year}-\d{{4}}$")
        self.assertNotEqual(hallazgo.codigo, "SAC-NOC-2025-0200")
        self.assertEqual(hallazgo.estado, "CERRADO")
        accion = hallazgo.ciclos.get().acciones.get()
        self.assertEqual(accion.codigo, f"{hallazgo.codigo}-A01")
        self.assertEqual(accion.responsable, self.usuario)
        self.assertEqual(accion.porcentaje_avance, 100)
        self.assertEqual(accion.resultado_esperado, "Corregir el registro")
        self.assertEqual(hallazgo.ciclos.get().evaluaciones.get().resultado, "EFICAZ")

    def test_importa_borrador_con_solo_las_siete_columnas_obligatorias(self):
        hojas = {
            "Carga masiva": [{
                "__fila__": 2,
                "Código hallazgo *": "SAC-NOC-2025-0201",
                "Título *": "Hallazgo pendiente desde plantilla reducida",
                "Tipo (código) *": "NOC",
                "Proceso *": "Facturacion",
                "Responsable hallazgo *": self.usuario.username,
                "Fecha registro *": timezone.now().replace(microsecond=0).isoformat(),
                "Estado hallazgo *": "BORRADOR",
            }]
        }

        resumen = ImportadorMasivo(
            hojas=hojas, ejecutado_por=self.admin
        ).preparar().guardar()

        self.assertEqual(resumen["hallazgos"], 1)
        hallazgo = Hallazgo.objects.get()
        self.assertRegex(hallazgo.codigo, rf"^SAC-NOC-{timezone.localdate().year}-\d{{4}}$")
        self.assertFalse(hallazgo.aplica_impacto)
        self.assertEqual(hallazgo.responsable, self.usuario)
        self.assertEqual(hallazgo.registrado_por, self.usuario)
        self.assertFalse(hallazgo.ciclos.exists())

    def test_acepta_formato_ntt_con_nombres_visibles_y_porcentajes_excel(self):
        hoy = timezone.localdate()
        hojas = {
            "Carga masiva": [{
                "__fila__": 2,
                "Código hallazgo *": "NTT-001",
                "Título *": "Hallazgo histórico NTT",
                "Descripción hallazgo": "Descripción del hallazgo",
                "Tipo (código) *": "NOC",
                "Fuente (código)": "Hallazgo de auditoría",
                "Proceso *": "Facturación",
                "Responsable hallazgo *": "Walter Ramirez",
                "Registrado por": "Juan Carlos Tello",
                "Fecha registro *": hoy,
                "Estado hallazgo *": "",
                "Aplica impacto *": "NO",
                "Es crítica": "SI",
                "Origen tecnológico": "NO",
                "Causa raíz": "MANO_DE_OBRA",
                "Descripcion de la causa": "Faltó capacitación específica.",
                "Tipo compromiso": "ACCION_CORRECTIVA",
                "Descripción compromiso": "Capacitar al equipo",
                "Responsable compromiso": "Walter Ramírez",
                "Inicio compromiso": hoy,
                "Fecha fin estimada": hoy + timedelta(days=10),
                "Estado compromiso": "PENDIENTE",
                "Avance %": 0.9,
                "Comentario compromiso": "Avance informado por el responsable",
            }]
        }

        resumen = ImportadorMasivo(
            hojas=hojas, ejecutado_por=self.admin
        ).preparar().guardar()

        self.assertEqual(resumen["hallazgos"], 1)
        hallazgo = Hallazgo.objects.get()
        self.assertRegex(hallazgo.codigo, rf"^SAC-NOC-{hoy.year}-\d{{4}}$")
        self.assertNotEqual(hallazgo.codigo, "NTT-001")
        self.assertEqual(hallazgo.fuente_deteccion, self.fuente)
        self.assertEqual(hallazgo.registrado_por, self.admin)
        self.assertEqual(hallazgo.estado, "EN_IMPLEMENTACION")
        ciclo = hallazgo.ciclos.get()
        self.assertEqual(ciclo.control["causa_categoria"], "MANO_OBRA")
        self.assertEqual(ciclo.causa_raiz, "Faltó capacitación específica.")
        accion = ciclo.acciones.get()
        self.assertEqual(accion.codigo, f"{hallazgo.codigo}-A01")
        self.assertEqual(accion.tipo, "CORRECTIVA")
        self.assertEqual(accion.estado, "EN_PROCESO")
        self.assertEqual(accion.porcentaje_avance, 90)
        self.assertEqual(accion.fet_inicial, hoy + timedelta(days=10))

    def test_genera_codigo_por_tipo_y_anio_usando_la_referencia_solo_para_agrupar(self):
        anio = 2024
        tipos = {}
        for orden, (codigo, nombre) in enumerate((
            ("INC", "Incidente"),
            ("PBI", "PBI"),
            ("SNC", "Salida no conforme"),
        ), start=2):
            tipos[codigo] = Catalogo.objects.create(clase="TIPO", codigo=codigo, nombre=nombre, orden=orden)
        Hallazgo.objects.create(
            codigo="SAC-INC-2024-0042",
            titulo="Código existente",
            tipo_registro=tipos["INC"],
            proceso=self.proceso,
            responsable=self.usuario,
            registrado_por=self.admin,
            updated_by=self.admin,
            aplica_impacto=False,
            justificacion_no_impacto="Registro previo",
            estado="BORRADOR",
        )
        CorrelativoSAC.objects.create(anio=anio, ambito="NOC", ultimo_numero=7)
        filas = []
        for referencia, tipo in (("1", "INC"), ("2", "NOC"), ("3", "PBI"), ("4", "SNC")):
            filas.append({
                "__fila__": len(filas) + 2,
                "Código hallazgo *": referencia,
                "Título *": f"Hallazgo {tipo}",
                "Tipo (código) *": tipo,
                "Proceso *": "Facturacion",
                "Responsable hallazgo *": self.usuario.username,
                "Fecha registro *": f"{anio}-06-15",
                "Estado hallazgo *": "BORRADOR",
            })

        resumen = ImportadorMasivo(
            hojas={"Carga masiva": filas}, ejecutado_por=self.admin
        ).preparar().guardar()

        self.assertEqual(resumen["hallazgos"], 4)
        self.assertEqual(
            {item["referencia"] for item in resumen["codigos_generados"]},
            {"1", "2", "3", "4"},
        )
        self.assertSetEqual(
            set(Hallazgo.objects.filter(titulo__startswith="Hallazgo ").values_list("codigo", flat=True)),
            {
                "SAC-INC-2024-0043",
                "SAC-NOC-2024-0008",
                "SAC-PBI-2024-0001",
                "SAC-SNC-2024-0001",
            },
        )

    def test_referencia_repetida_crea_un_hallazgo_con_compromisos_consecutivos(self):
        hoy = timezone.localdate()
        base = {
            "Código hallazgo *": "1",
            "Título *": "Hallazgo con dos compromisos",
            "Tipo (código) *": "NOC",
            "Proceso *": "Facturacion",
            "Responsable hallazgo *": self.usuario.username,
            "Fecha registro *": hoy,
            "Estado hallazgo *": "",
            "Tipo compromiso": "ACCION_CORRECTIVA",
            "Responsable compromiso": self.usuario.username,
            "Inicio compromiso": hoy,
            "Fecha fin estimada": hoy + timedelta(days=10),
            "Estado compromiso": "PENDIENTE",
            "Avance %": 0,
        }
        filas = [
            {"__fila__": 2, **base, "Descripción compromiso": "Primera acción"},
            {"__fila__": 3, **base, "Descripción compromiso": "Segunda acción"},
        ]

        ImportadorMasivo(
            hojas={"Carga masiva": filas}, ejecutado_por=self.admin
        ).preparar().guardar()

        hallazgo = Hallazgo.objects.get()
        self.assertRegex(hallazgo.codigo, rf"^SAC-NOC-{hoy.year}-\d{{4}}$")
        self.assertListEqual(
            list(hallazgo.ciclos.get().acciones.order_by("codigo").values_list("codigo", flat=True)),
            [f"{hallazgo.codigo}-A01", f"{hallazgo.codigo}-A02"],
        )
