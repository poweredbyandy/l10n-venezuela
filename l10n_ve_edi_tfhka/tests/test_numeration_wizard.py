from datetime import date
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTfhkaNumerationWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        params = cls.env["ir.config_parameter"].sudo()
        params.set_param("l10n_ve_edi_tfhka.username", "demo")
        params.set_param("l10n_ve_edi_tfhka.password", "demo")
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "TFHKA sales",
                "code": "TFHK",
                "type": "sale",
                "l10n_ve_edi_provider": "tfhka",
                "l10n_ve_edi_tfhka_serie": "A-1",
            }
        )
        cls.service_class = type(cls.env["l10n_ve_edi_tfhka.api.service"])

    def _new_wizard(self, **vals):
        values = {
            "journal_id": self.journal.id,
            "period_date": date(2026, 10, 15),
        }
        values.update(vals)
        return self.env["l10n_ve_edi_tfhka.numeration.wizard"].create(values)

    def _patch_service(self, query_response, assign_response=None):
        patchers = [
            patch.object(
                self.service_class,
                "authenticate",
                return_value={"token": "token"},
            ),
            patch.object(
                self.service_class,
                "query_numerations",
                return_value=query_response,
            ),
            patch.object(
                self.service_class,
                "assign_numerations",
                return_value=assign_response or {"codigo": "200"},
            ),
        ]
        return [self.startPatcher(patcher) for patcher in patchers]

    def test_default_range_follows_invoice_numbering(self):
        wizard = self._new_wizard()
        self.assertEqual(wizard.serie, "A1")
        self.assertEqual(wizard.number_start, "01202610000001")
        self.assertEqual(wizard.number_end, "01202610999999")

    def test_default_range_with_environment_digit(self):
        self.journal.l10n_ve_edi_tfhka_environment_digit = "3"
        wizard = self._new_wizard(document_type="02")
        self.assertEqual(wizard.number_start, "02202610300001")
        self.assertEqual(wizard.number_end, "02202610399999")

    def test_default_range_for_withholding(self):
        wizard = self._new_wizard(document_type="05")
        self.assertEqual(wizard.number_start, "20261000000001")
        self.assertEqual(wizard.number_end, "20261099999999")

    def test_query_without_numeration(self):
        self._patch_service({"codigo": "201", "mensaje": "No existen"})
        wizard = self._new_wizard()
        wizard.action_query()
        self.assertEqual(wizard.numeration_state, "missing")

    def test_query_and_assign_when_missing(self):
        _auth, _query, assign = self._patch_service({"codigo": "201"})
        wizard = self._new_wizard()
        wizard.action_query_and_assign()
        self.assertEqual(wizard.numeration_state, "assigned")
        payload = assign.call_args.args[0]
        self.assertEqual(
            payload["detalleAsignacion"][0],
            {
                "serie": "A1",
                "tipoDocumento": "01",
                "numeroDocumentoInicio": "01202610000001",
                "numeroDocumentoFin": "01202610999999",
            },
        )

    def test_query_and_assign_skips_when_available(self):
        _auth, _query, assign = self._patch_service({"codigo": "200"})
        wizard = self._new_wizard()
        wizard.action_query_and_assign()
        self.assertEqual(wizard.numeration_state, "available")
        assign.assert_not_called()

    def test_invalid_range_is_rejected(self):
        self._patch_service({"codigo": "201"})
        wizard = self._new_wizard(number_start="0120261099", number_end="0120261001")
        with self.assertRaises(UserError):
            wizard.action_query_and_assign()
