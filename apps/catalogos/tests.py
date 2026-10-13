from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase

from apps.catalogos.models import Proceso, Subproceso
from apps.catalogos.services import actividades_para, sincronizar_catalogo_identificacion
from config.oracle_backend.base import DatabaseWrapper


class OracleIdentifierTests(SimpleTestCase):
    def test_nombre_largo_de_auditoria_no_se_trunca_en_oracle(self):
        nombre = "tbl_auditoria_administracion_nc"

        self.assertEqual(
            DatabaseWrapper.ops_class(None).quote_name(nombre),
            '"TBL_AUDITORIA_ADMINISTRACION_NC"',
        )

    def test_backend_oracle_19c_admite_identificadores_de_128_caracteres(self):
        self.assertEqual(DatabaseWrapper.ops_class(None).max_name_length(), 128)


class CatalogoIdentificacionTests(TestCase):
    def test_sincronizacion_reemplaza_opciones_sin_borrar_historicos(self):
        anterior = Proceso.objects.create(nombre="Proceso anterior")
        legado = Proceso.objects.create(nombre="Facturación", gerencia="Facturación")
        subproceso_anterior = Subproceso.objects.create(
            proceso=anterior,
            nombre="Subproceso anterior",
        )

        call_command("sincronizar_catalogo_identificacion", stdout=StringIO())

        anterior.refresh_from_db()
        subproceso_anterior.refresh_from_db()
        self.assertFalse(anterior.activo)
        self.assertFalse(subproceso_anterior.activo)
        proceso = Proceso.objects.get(nombre="Facturacion", activo=True)
        self.assertEqual(proceso.gerencia, legado.gerencia)
        self.assertEqual(
            list(proceso.subprocesos.filter(activo=True).values_list("nombre", flat=True).order_by("pk")),
            ["Emision", "Generacion", "Distribucion"],
        )
        emision = proceso.subprocesos.get(nombre="Emision")
        self.assertEqual(
            actividades_para(proceso, emision),
            (
                "Cierre de tráfico",
                "Pre-billing",
                "Billing",
                "traslado de documentos al oac",
                "Co-billing",
                "Estados de documentos en SUNAT",
                "Generacion de Nota de Credito retenidos",
                "Generacion de Reportes",
                "Carga de tramas a Sunat SUNAT",
            ),
        )

        segunda = sincronizar_catalogo_identificacion()
        self.assertEqual(segunda["procesos_creados"], 0)
        self.assertEqual(segunda["procesos_activados"], 0)
        self.assertEqual(segunda["procesos_inactivados"], 0)
        self.assertEqual(segunda["subprocesos_creados"], 0)
        self.assertEqual(segunda["subprocesos_activados"], 0)
        self.assertEqual(segunda["subprocesos_inactivados"], 0)
        self.assertEqual(segunda["actividades_creadas"], 0)
        self.assertEqual(segunda["actividades"], 18)
