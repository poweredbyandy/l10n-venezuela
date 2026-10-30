# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

# Document rate ~872.39 Bs/USD (ferreagro S11562 / INV/2026/02107).
FERREAGRO_LIKE_RATE = 0.0011462727737176158


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

    def _sale_tax_0(self):
        country = self.env.company.account_fiscal_country_id
        tax_group = self.env["account.tax.group"].create(
            {
                "name": "Sale Test IVA 0",
                "company_id": self.env.company.id,
                "country_id": country.id,
            }
        )
        return self.percent_tax(
            0.0,
            type_tax_use="sale",
            tax_group_id=tax_group.id,
            country_id=country.id,
        )

    def _invoice_native_company_base(self, order):
        Move = self.env["account.move"]
        company = order.company_id.currency_id
        stub = Move.new(
            {
                "company_id": order.company_id.id,
                "currency_id": order.currency_id.id,
                "move_type": "out_invoice",
                "invoice_currency_rate": order.currency_rate,
            }
        )
        total = 0.0
        for line in order.order_line.filtered(lambda order_line: not order_line.display_type):
            total = company.round(
                total
                + stub._l10n_ve_company_line_subtotal_from_foreign_unit(
                    line.price_unit,
                    line.product_uom_qty,
                    discount=line.discount,
                    rate=order.currency_rate,
                )
            )
        return total

    def _invoice_from_order_lines(self, order):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": order.partner_id.id,
                "invoice_date": fields.Date.to_date(order.date_order),
                "date": fields.Date.to_date(order.date_order),
                "currency_id": order.currency_id.id,
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
                        lambda order_line: not order_line.display_type
                    )
                ],
            }
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

        expected_base = self._invoice_native_company_base(order)
        company = order.company_id.currency_id
        self.assertAlmostEqual(so_totals["base_amount"], expected_base, places=2)
        self.assertAlmostEqual(
            so_totals["tax_amount"], company.round(expected_base * 0.16), places=2
        )

        invoice = self._invoice_from_order_lines(order)
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

    def test_sale_tax_totals_ferreagro_like_fractional_prices(self):
        """Regression S11562: subtotal/rate must not drive the SO Bs footer."""
        tax_0 = self._sale_tax_0()
        tax_16 = self._sale_tax_16()
        ves = self.setup_other_currency(
            "VES",
            rates=[("2016-01-01", 1.0), ("2026-10-06", 1.0)],
        )
        self.env.company.write({"currency_id": ves.id})
        usd = self.setup_other_currency(
            "USD",
            rates=[
                ("2016-01-01", FERREAGRO_LIKE_RATE),
                ("2026-10-06", FERREAGRO_LIKE_RATE),
            ],
        )
        products = [
            self.env["product.product"].create(
                {"name": "BUS9115", "list_price": 0.83, "taxes_id": [(6, 0, tax_16.ids)]}
            ),
            self.env["product.product"].create(
                {
                    "name": "AM50X11/2",
                    "list_price": 4.0,
                    "taxes_id": [(6, 0, tax_0.ids)],
                }
            ),
            self.env["product.product"].create(
                {"name": "413306", "list_price": 0.87, "taxes_id": [(6, 0, tax_16.ids)]}
            ),
        ]
        lines = [
            (products[0], 0.946615),
            (products[1], 4.562),
            (products[2], 0.992235),
        ]
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "date_order": fields.Datetime.to_datetime("2026-10-06 14:53:48"),
                "currency_id": usd.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": price_unit,
                        },
                    )
                    for product, price_unit in lines
                ],
            }
        )
        self.assertAlmostEqual(order.amount_total, 6.81, places=2)
        self.assertAlmostEqual(order.currency_rate, FERREAGRO_LIKE_RATE, places=10)
        company = order.company_id.currency_id
        naive_base = 0.0
        for line in order.order_line:
            naive_base = company.round(
                naive_base + company.round(line.price_subtotal / order.currency_rate)
            )
        native_base = self._invoice_native_company_base(order)
        self.assertAlmostEqual(naive_base, 5670.55, places=2)
        self.assertAlmostEqual(native_base, 5671.3, places=2)
        self.assertNotAlmostEqual(naive_base, native_base, places=2)

        invoice = self._invoice_from_order_lines(order)
        invoice.action_post()
        inv_totals = invoice.tax_totals
        so_totals = order.tax_totals
        self.assertAlmostEqual(so_totals["total_amount_currency"], 6.81, places=2)
        self.assertAlmostEqual(inv_totals["total_amount_currency"], 6.81, places=2)
        self.assertAlmostEqual(so_totals["total_amount"], 5941.93, places=2)
        self.assertAlmostEqual(inv_totals["total_amount"], 5941.93, places=2)
        self.assertAlmostEqual(
            so_totals["total_amount"], inv_totals["total_amount"], places=2
        )
