# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestPurchaseTaxTotalsCompany(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write(
            {
                "account_fiscal_country_id": cls.env.ref("base.ve").id,
                "account_purchase_tax_id": False,
            }
        )
        cls.foreign_currency = cls.setup_other_currency(
            "EUR", rates=[("2016-01-01", 2.0), ("2024-02-01", 4.0)]
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "PO Currency Product",
                "list_price": 1.0,
                "purchase_ok": True,
                "supplier_taxes_id": [(6, 0, [])],
            }
        )

    def _purchase_tax_16(self):
        country = self.env.company.account_fiscal_country_id
        tax_group = self.env["account.tax.group"].create(
            {
                "name": "Purchase Test IVA",
                "company_id": self.env.company.id,
                "country_id": country.id,
            }
        )
        return self.percent_tax(
            16.0,
            type_tax_use="purchase",
            tax_group_id=tax_group.id,
            country_id=country.id,
        )

    def test_purchase_tax_totals_company_matches_bill(self):
        """RFQ company TaxTotals follow per-line round like the vendor bill."""
        tax_16 = self._purchase_tax_16()
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_a.id,
                "date_order": fields.Datetime.to_datetime("2024-01-10 10:00:00"),
                "currency_id": self.foreign_currency.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "Line A",
                            "product_qty": 32.0,
                            "price_unit": 4.473315,
                            "taxes_id": [(6, 0, tax_16.ids)],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "Line B",
                            "product_qty": 1.0,
                            "price_unit": 10.99999999,
                            "taxes_id": [(6, 0, tax_16.ids)],
                        },
                    ),
                ],
            }
        )
        self.assertAlmostEqual(order.currency_rate, 2.0)
        po_totals = order.tax_totals
        self.assertTrue(po_totals.get("display_in_company_currency"))

        expected_base = 0.0
        company = order.company_id.currency_id
        for line in order.order_line.filtered(lambda line: not line.display_type):
            expected_base = company.round(
                expected_base + company.round(line.price_subtotal / order.currency_rate)
            )
        self.assertAlmostEqual(po_totals["base_amount"], expected_base, places=2)
        self.assertAlmostEqual(
            po_totals["tax_amount"], company.round(expected_base * 0.16), places=2
        )

        self.product.write({"purchase_method": "purchase"})
        order.button_confirm()
        action = order.action_create_invoice()
        bill = self.env["account.move"].browse(action["res_id"])
        bill.invoice_date = fields.Date.to_date("2024-01-10")
        bill.invoice_currency_rate = bill.expected_currency_rate
        self.assertAlmostEqual(bill.invoice_currency_rate, 2.0)
        bill_totals = bill.tax_totals
        self.assertAlmostEqual(
            bill_totals["base_amount_currency"],
            po_totals["base_amount_currency"],
            places=2,
        )
        self.assertAlmostEqual(
            bill_totals["base_amount"], po_totals["base_amount"], places=2
        )
        self.assertAlmostEqual(
            bill_totals["tax_amount"], po_totals["tax_amount"], places=2
        )
        self.assertAlmostEqual(
            bill_totals["total_amount"], po_totals["total_amount"], places=2
        )
