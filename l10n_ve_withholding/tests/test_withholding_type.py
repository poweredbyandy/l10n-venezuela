from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestWithholdingType(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.withholding_type_model = cls.env["account.withholding.type"]

    def test_default_withholding_type_is_first_by_sequence(self):
        first = self.withholding_type_model.search(
            [("state", "=", True)], order="sequence, id", limit=1
        )
        self.assertTrue(first)
        self.assertEqual(
            self.withholding_type_model._get_default_withholding_type_id(),
            first.id,
        )

    def test_partner_create_gets_default_withholding_type(self):
        first = self.withholding_type_model.search(
            [("state", "=", True)], order="sequence, id", limit=1
        )
        self.assertTrue(first)
        partner = self.env["res.partner"].create({"name": "Proveedor prueba retención"})
        self.assertEqual(partner.withholding_type_id, first)

    def test_partner_without_withholding_type_has_no_fallback(self):
        partner = self.env["res.partner"].create(
            {"name": "Proveedor sin tipo", "withholding_type_id": False}
        )
        self.assertFalse(partner.withholding_type_id)
        self.assertFalse(partner._l10n_ve_get_withholding_type())
