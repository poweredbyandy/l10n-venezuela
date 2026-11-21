from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestIslrSupplierPartnerDomain(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ve = cls.env.ref("base.ve")
        cls.partner_domain = (
            cls.env["res.partner"]._l10n_ve_islr_supplier_partner_domain()
        )

    def _search_partners(self):
        return self.env["res.partner"].search(self.partner_domain)

    def test_supplier_with_classifiable_type_is_allowed(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Proveedor ISLR aplicable",
                "country_id": self.ve.id,
                "vat": "J334455667",
                "supplier_rank": 1,
            }
        )
        self.assertEqual(partner.l10n_ve_person_type, "pj_domiciled")
        self.assertIn(partner, self._search_partners())

    def test_customer_only_is_excluded(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente sin compras",
                "country_id": self.ve.id,
                "vat": "J334455667",
                "customer_rank": 1,
                "supplier_rank": 0,
            }
        )
        self.assertNotIn(partner, self._search_partners())

    def test_child_contact_is_excluded(self):
        parent = self.env["res.partner"].create(
            {
                "name": "Proveedor padre",
                "country_id": self.ve.id,
                "vat": "J334455667",
                "supplier_rank": 1,
            }
        )
        child = self.env["res.partner"].create(
            {
                "name": "Dirección de entrega",
                "parent_id": parent.id,
                "country_id": self.ve.id,
            }
        )
        self.assertNotIn(child, self._search_partners())
