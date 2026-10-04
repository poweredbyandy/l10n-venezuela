# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.l10n_ve_validate_partner_vat_format = True

    def test_check_vat_ve_valid_formats(self):
        partner = self.env["res.partner"].create(
            {"name": "Test Partner", "country_id": self.env.ref("base.ve").id}
        )
        valid_vats = [
            "V12345678",
            "V7440703",
            "E12345678",
            "J12345678",
            "G12345678",
            "J-12.345.678-9",
        ]
        for vat in valid_vats:
            partner.vat = vat
            self.assertTrue(
                partner.check_vat_ve(partner.vat), f"VAT {vat} should be valid"
            )

    def test_check_vat_ve_invalid_formats(self):
        partner = self.env["res.partner"].create(
            {"name": "Test Partner", "country_id": self.env.ref("base.ve").id}
        )
        invalid_vats = ["12345678", "X12345678", "V123", "V12345678901"]
        for vat in invalid_vats:
            self.assertFalse(partner.check_vat_ve(vat), f"VAT {vat} should be invalid")

    def test_ve_vat_constraint_allows_invalid_when_not_customer_nor_supplier(self):
        partner = self.env["res.partner"].create(
            {"name": "Test Partner", "country_id": self.env.ref("base.ve").id}
        )
        partner.write({"vat": "V123"})
        self.assertEqual(partner.vat, "V123")

    def test_ve_vat_constraint_rejects_invalid_on_write_when_customer(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "country_id": self.env.ref("base.ve").id,
                "customer_rank": 1,
            }
        )
        with self.assertRaises(ValidationError):
            partner.write({"vat": "V123"})

    def test_ve_vat_constraint_can_be_disabled(self):
        self.env.company.l10n_ve_validate_partner_vat_format = False
        partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
                "country_id": self.env.ref("base.ve").id,
                "customer_rank": 1,
            }
        )
        partner.write({"vat": "V123"})
        self.assertEqual(partner.vat, "V123")

    def test_ve_vat_constraint_skipped_with_context(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Sync partner",
                "country_id": self.env.ref("base.ve").id,
                "customer_rank": 1,
            }
        )
        partner.with_context(skip_l10n_ve_vat_rif_format_check=True).write(
            {"vat": "no-rif"}
        )
        self.assertTrue(partner.vat.endswith("no-rif"))

    def test_check_vat_ve_keeps_base_vat_checksum_formats(self):
        partner = self.env["res.partner"]
        self.assertTrue(partner.check_vat_ve("V-12.345.678-1"))
        self.assertTrue(partner.check_vat_ve("V123456781"))

    def test_base_vat_skips_ve_partner_when_validation_disabled(self):
        self.env.company.l10n_ve_validate_partner_vat_format = False
        partner = self.env["res.partner"].create(
            {
                "name": "Partner VE",
                "country_id": self.env.ref("base.ve").id,
                "customer_rank": 1,
                "is_company": True,
            }
        )
        partner.write({"vat": "ABC123"})
        self.assertTrue(partner.vat.endswith("ABC123"))

    def test_base_vat_rejects_invalid_ve_customer(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Partner VE",
                "country_id": self.env.ref("base.ve").id,
                "customer_rank": 1,
                "is_company": True,
            }
        )
        with self.assertRaises(ValidationError):
            partner.write({"vat": "ABC123"})
