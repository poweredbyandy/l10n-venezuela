from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestTypePerson(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.type_person_model = cls.env["type.person"]

    def test_default_type_person_is_first_by_sequence(self):
        first = self.type_person_model.search(
            [("state", "=", True)], order="sequence, id", limit=1
        )
        self.assertTrue(first)
        self.assertEqual(
            self.type_person_model._get_default_type_person_id(),
            first.id,
        )

    def test_partner_create_gets_default_type_person(self):
        first = self.type_person_model.search(
            [("state", "=", True)], order="sequence, id", limit=1
        )
        self.assertTrue(first)
        partner = self.env["res.partner"].create({"name": "Contacto prueba"})
        self.assertEqual(partner.type_person_id, first)
