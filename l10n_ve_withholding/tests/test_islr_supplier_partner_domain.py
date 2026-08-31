from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestIslrSupplierPartnerDomain(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.type_person_pn = cls.env.ref(
            "l10n_ve_withholding.type_person_l10n_ve_withholding"
        )
        Partner = cls.env["res.partner"]
        cls.partner_domain = Partner._l10n_ve_islr_supplier_partner_domain()

    def _search_partners(self):
        return self.env["res.partner"].search(self.partner_domain)

    def test_supplier_with_applicable_type_person_is_allowed(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Proveedor ISLR aplicable",
                "supplier_rank": 1,
                "type_person_id": self.type_person_pn.id,
            }
        )
        self.assertIn(partner, self._search_partners())

    def test_customer_only_is_excluded(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente sin compras",
                "customer_rank": 1,
                "supplier_rank": 0,
                "type_person_id": self.type_person_pn.id,
            }
        )
        self.assertNotIn(partner, self._search_partners())

    def test_partner_without_type_person_is_excluded(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Proveedor sin tipo de persona",
                "supplier_rank": 1,
                "type_person_id": False,
            }
        )
        self.assertNotIn(partner, self._search_partners())

    def test_child_contact_is_excluded(self):
        parent = self.env["res.partner"].create(
            {
                "name": "Proveedor razon social",
                "supplier_rank": 1,
                "type_person_id": self.type_person_pn.id,
            }
        )
        child = self.env["res.partner"].create(
            {
                "name": "Contacto hijo",
                "parent_id": parent.id,
                "type": "contact",
                "supplier_rank": 1,
                "type_person_id": self.type_person_pn.id,
            }
        )
        partners = self._search_partners()
        self.assertIn(parent, partners)
        self.assertNotIn(child, partners)

    def test_inactive_type_person_is_excluded(self):
        inactive_type = self.env["type.person"].create(
            {"name": "Tipo persona inactivo", "state": False}
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Proveedor tipo inactivo",
                "supplier_rank": 1,
                "type_person_id": inactive_type.id,
            }
        )
        self.assertNotIn(partner, self._search_partners())

    def test_type_person_without_payment_concept_is_excluded(self):
        unused_type = self.env["type.person"].create(
            {"name": "Tipo sin concepto", "state": True}
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Proveedor sin concepto ISLR",
                "supplier_rank": 1,
                "type_person_id": unused_type.id,
            }
        )
        self.assertNotIn(partner, self._search_partners())

    def test_retention_domain_only_applies_to_supplier_islr(self):
        supplier_retention = self.env["account.retention"].new(
            {"type": "in_invoice", "type_retention": "islr"}
        )
        self.assertEqual(
            supplier_retention.islr_supplier_partner_domain,
            self.partner_domain,
        )
        client_retention = self.env["account.retention"].new(
            {"type": "out_invoice", "type_retention": "islr"}
        )
        self.assertEqual(client_retention.islr_supplier_partner_domain, [])
        iva_retention = self.env["account.retention"].new(
            {"type": "in_invoice", "type_retention": "iva"}
        )
        self.assertEqual(iva_retention.islr_supplier_partner_domain, [])
