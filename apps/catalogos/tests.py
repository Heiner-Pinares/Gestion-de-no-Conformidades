from io import StringIO

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.models import Usuario
from apps.catalogos.models import Catalogo, CategoriaCausa, Proceso, Subproceso, TipoRegistro
from apps.hallazgos.models import Hallazgo
from apps.catalogos.services import (
    TIPO_COPIA, TIPO_PARA, actividades_para, correos_queryset,
    destinatarios_adicionales, sincronizar_catalogo_identificacion,
)
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


class CatalogoDeletionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(
            "admin.catalogos",
            password="ClaveSoloParaTests-2026!",
        )
        cls.admin.add_role("ADMINISTRADOR")
        cls.usuario = Usuario.objects.create_user(
            "usuario.catalogos",
            password="ClaveSoloParaTests-2026!",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_admin_elimina_proceso_inactivo_sin_referencias(self):
        proceso = Proceso.objects.create(nombre="Proceso descartable", activo=False)
        listado = self.client.get(reverse("catalogos"), {
            "tipo": "procesos", "estado": "inactivo",
        })
        self.assertContains(
            listado,
            reverse("catalogo_eliminar", args=["procesos", proceso.pk]),
        )

        respuesta = self.client.post(
            reverse("catalogo_eliminar", args=["procesos", proceso.pk]),
            follow=True,
        )

        self.assertFalse(Proceso.objects.filter(pk=proceso.pk).exists())
        self.assertContains(respuesta, "fue eliminado del catálogo")

    def test_no_elimina_activo_y_elimina_jerarquia_sin_hallazgos(self):
        activo = Proceso.objects.create(nombre="Proceso activo")
        respuesta = self.client.post(
            reverse("catalogo_eliminar", args=["procesos", activo.pk]),
            follow=True,
        )
        self.assertTrue(Proceso.objects.filter(pk=activo.pk).exists())
        self.assertContains(respuesta, "Primero marque el registro como inactivo")

        proceso = Proceso.objects.create(nombre="Proceso con jerarquía", activo=False)
        subproceso = Subproceso.objects.create(
            proceso=proceso, nombre="Subproceso sin hallazgos",
        )
        actividad = Catalogo.objects.create(
            clase="CATEGORIA",
            codigo=f"ACT_{subproceso.pk}_PRUEBA",
            nombre="Actividad sin hallazgos",
            activo=False,
        )
        respuesta = self.client.post(
            reverse("catalogo_eliminar", args=["procesos", proceso.pk]),
            follow=True,
        )
        self.assertFalse(Proceso.objects.filter(pk=proceso.pk).exists())
        self.assertFalse(Subproceso.objects.filter(pk=subproceso.pk).exists())
        self.assertFalse(Catalogo.objects.filter(pk=actividad.pk).exists())
        self.assertContains(respuesta, "junto con 1 subproceso y 1 actividad")

    def test_no_elimina_proceso_utilizado_por_hallazgo(self):
        proceso = Proceso.objects.create(nombre="Proceso histórico", activo=False)
        tipo = TipoRegistro.objects.create(codigo="INC", nombre="Incidente")
        Hallazgo.objects.create(
            codigo="SAC-INC-2026-9999",
            titulo="Hallazgo histórico",
            tipo_registro=tipo,
            proceso=proceso,
            responsable=self.usuario,
            registrado_por=self.usuario,
            updated_by=self.usuario,
        )

        respuesta = self.client.post(
            reverse("catalogo_eliminar", args=["procesos", proceso.pk]),
            follow=True,
        )

        self.assertTrue(Proceso.objects.filter(pk=proceso.pk).exists())
        self.assertContains(respuesta, "1 hallazgo lo utiliza")

    def test_eliminacion_exige_post_y_administrador(self):
        proceso = Proceso.objects.create(nombre="Proceso restringido", activo=False)
        url = reverse("catalogo_eliminar", args=["procesos", proceso.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

        self.client.force_login(self.usuario)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertTrue(Proceso.objects.filter(pk=proceso.pk).exists())


class CorreosCompromisosCatalogoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_user(
            "admin.correos",
            password="ClaveSoloParaTests-2026!",
            email="admin.correos@claro.com.pe",
        )
        cls.admin.add_role("ADMINISTRADOR")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_admin_agrega_quita_y_restaura_destinatarios(self):
        inicio = self.client.get(reverse("catalogos"))
        self.assertContains(inicio, "Correos de compromisos")

        agregado = self.client.post(reverse("catalogos_correos"), {
            "accion": "agregar",
            "tipo": TIPO_PARA,
            "correo": "calidad.adicional@claro.com.pe",
        })
        self.assertRedirects(agregado, reverse("catalogos_correos"))
        registro = correos_queryset(TIPO_PARA).get(
            nombre="calidad.adicional@claro.com.pe"
        )
        self.assertTrue(registro.activo)
        self.assertTrue(registro.codigo.startswith("CFG_MAIL_TO_"))

        quitado = self.client.post(reverse("catalogos_correos"), {
            "accion": "cambiar_estado",
            "registro_id": registro.pk,
            "activo": "0",
        })
        self.assertRedirects(quitado, reverse("catalogos_correos"))
        registro.refresh_from_db()
        self.assertFalse(registro.activo)

        restaurado = self.client.post(reverse("catalogos_correos"), {
            "accion": "agregar",
            "tipo": TIPO_PARA,
            "correo": "CALIDAD.ADICIONAL@claro.com.pe",
        })
        self.assertRedirects(restaurado, reverse("catalogos_correos"))
        registro.refresh_from_db()
        self.assertTrue(registro.activo)
        self.assertEqual(correos_queryset(TIPO_PARA).count(), 1)

    def test_valida_email_y_oculta_configuracion_del_analisis_6m(self):
        respuesta = self.client.post(reverse("catalogos_correos"), {
            "accion": "agregar",
            "tipo": TIPO_COPIA,
            "correo": "correo-invalido",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Introduzca una dirección de correo electrónico válida")
        self.assertFalse(correos_queryset().exists())

        self.client.post(reverse("catalogos_correos"), {
            "accion": "agregar",
            "tipo": TIPO_COPIA,
            "correo": "auditoria@claro.com.pe",
        })
        self.assertEqual(
            destinatarios_adicionales()[TIPO_COPIA],
            ["auditoria@claro.com.pe"],
        )
        self.assertFalse(
            CategoriaCausa.objects.filter(nombre="auditoria@claro.com.pe").exists()
        )
        self.assertTrue(
            Catalogo.objects.filter(nombre="auditoria@claro.com.pe").exists()
        )
