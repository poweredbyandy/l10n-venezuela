# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestSaleTaxTotalsCompany(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write(
            {
                "account_fiscal_country_id": cls.env.ref("base.ve").id,
                "account_sale_tax_id": False,
            }
        )
        cls.foreign_currency = cls.setup_other_currency(
            "EUR", rates=[("2016-01-01", 2.0), ("2024-02-01", 4.0)]
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "SO Currency Product",
                "list_price": 1.0,
                "taxes_id": [(6, 0, [])],
            }
        )
        cls.pricelist = cls.env["product.pricelist"].create(
            {
                "name": "Foreign SO Pricelist",
                "currency_id": cls.foreign_currency.id,
                "company_id": cls.env.company.id,
            }
        )

    def _sale_tax_16(self):
        country = self.env.company.account_fiscal_country_id
        tax_group = self.env["account.tax.group"].create(
            {
                "name": "Sale Test IVA",
                "company_id": self.env.company.id,
                "country_id": country.id,
            }
        )
        return self.percent_tax(
            16.0,
            type_tax_use="sale",
            tax_group_id=tax_group.id,
            country_id=country.id,
        )

    def test_sale_tax_totals_company_matches_invoice(self):
        """Order company TaxTotals follow per-line round like the invoice."""
        tax_16 = self._sale_tax_16()
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "date_order": fields.Datetime.to_datetime("2024-01-10 10:00:00"),
                "pricelist_id": self.pricelist.id,
                "currency_id": self.foreign_currency.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "Line A",
                            "product_uom_qty": 32.0,
                            "price_unit": 4.473315,
                            "tax_id": [(6, 0, tax_16.ids)],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": "Line B",
                            "product_uom_qty": 1.0,
                            "price_unit": 10.99999999,
                            "tax_id": [(6, 0, tax_16.ids)],
                        },
                    ),
                ],
            }
        )
        self.assertAlmostEqual(order.currency_rate, 2.0)
        so_totals = order.tax_totals
        self.assertTrue(so_totals.get("display_in_company_currency"))

        expected_base = 0.0
        company = order.company_id.currency_id
        for line in order.order_line.filtered(lambda line: not line.display_type):
            expected_base = company.round(
                expected_base + company.round(line.price_subtotal / order.currency_rate)
            )
        self.assertAlmostEqual(so_totals["base_amount"], expected_base, places=2)
        self.assertAlmostEqual(
            so_totals["tax_amount"], company.round(expected_base * 0.16), places=2
        )

        # Same document lines/rate as a customer invoice built like account_currency.
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2024-01-10",
                "date": "2024-01-10",
                "currency_id": self.foreign_currency.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": line.name,
                            "quantity": line.product_uom_qty,
                            "price_unit": line.price_unit,
                            "tax_ids": [(6, 0, line.tax_id.ids)],
                        },
                    )
                    for line in order.order_line.filtered(
                        lambda line: not line.display_type
                    )
                ],
            }
        )
        self.assertAlmostEqual(invoice.invoice_currency_rate, order.currency_rate)
        inv_totals = invoice.tax_totals
        self.assertAlmostEqual(
            inv_totals["base_amount_currency"],
            so_totals["base_amount_currency"],
            places=2,
        )
        self.assertAlmostEqual(
            inv_totals["base_amount"], so_totals["base_amount"], places=2
        )
        self.assertAlmostEqual(
            inv_totals["tax_amount"], so_totals["tax_amount"], places=2
        )
        self.assertAlmostEqual(
            inv_totals["total_amount"], so_totals["total_amount"], places=2
        )
