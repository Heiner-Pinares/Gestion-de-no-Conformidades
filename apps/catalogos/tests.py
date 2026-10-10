from django.test import SimpleTestCase

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
