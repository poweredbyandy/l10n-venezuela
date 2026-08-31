from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestRetentionTaxableBase(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Proveedor base imponible",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J334455667",
                "supplier_rank": 1,
            }
        )
        cls.tax_16 = cls.company_data["default_tax_purchase"]
        cls.tax_exempt = cls.env["account.tax"].search(
            [
                ("company_id", "=", cls.env.company.id),
                ("type_tax_use", "=", "purchase"),
                ("amount", "=", 0),
            ],
            limit=1,
        )
        if not cls.tax_exempt:
            cls.tax_exempt = cls.env["account.tax"].create(
                {
                    "name": "IVA Exento test",
                    "amount": 0.0,
                    "amount_type": "percent",
                    "type_tax_use": "purchase",
                    "company_id": cls.env.company.id,
                    "country_id": cls.env.ref("base.ve").id,
                }
            )
        cls.payment_concept = cls.env.ref(
            "l10n_ve_withholding.payment_concept_one_l10n_ve_withholding"
        )
        cls.supplier.type_person_id = cls.env.ref(
            "l10n_ve_withholding.type_person_l10n_ve_withholding"
        )

    def _create_mixed_vendor_bill(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "invoice_date": "2026-01-15",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Linea gravada",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [Command.set(self.tax_16.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "name": "Linea exenta",
                            "quantity": 1.0,
                            "price_unit": 500.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [Command.set(self.tax_exempt.ids)],
                        }
                    ),
                ],
            }
        )
        bill.action_post()
        return bill

    def test_positive_tax_base_excludes_exempt_lines(self):
        bill = self._create_mixed_vendor_bill()
        self.assertEqual(bill.amount_untaxed, 1500.0)
        self.assertEqual(bill._l10n_ve_get_positive_tax_base_amount(), 1000.0)
        self.assertEqual(
            bill._l10n_ve_invoice_lines_with_positive_tax().mapped("price_subtotal"),
            [1000.0],
        )

    def test_islr_invoice_amount_excludes_exempt_lines(self):
        bill = self._create_mixed_vendor_bill()
        line = self.env["account.retention.line"].new(
            {
                "move_id": bill.id,
                "payment_concept_id": self.payment_concept.id,
            }
        )
        line._compute_related_fields()
        self.assertEqual(line.invoice_amount, 1000.0)
        self.assertNotEqual(line.invoice_amount, bill.amount_untaxed)

    def test_iva_invoice_amount_excludes_exempt_lines(self):
        bill = self._create_mixed_vendor_bill()
        lines_data = self.env["account.retention"].compute_retention_lines_data(bill)
        self.assertTrue(lines_data)
        self.assertEqual(sum(data["invoice_amount"] for data in lines_data), 1000.0)
        self.assertTrue(all(data["invoice_amount"] > 0 for data in lines_data))
