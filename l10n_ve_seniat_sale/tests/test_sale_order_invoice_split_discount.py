# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestSaleOrderInvoiceSplitDiscount(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.book = cls.env["account.book"].search(
            [("company_id", "=", cls.env.company.id)], limit=1
        )
        cls.book.l10n_ve_max_invoice_lines = 1
        cls.journal = cls.company_data["default_journal_sale"]
        cls.journal.write(
            {
                "l10n_ve_emission_medium": "digital",
                "l10n_ve_max_invoice_lines": 1,
            }
        )

    def _create_ve_product(self, name, price):
        tmpl = self.env["product.template"].create(
            {
                "name": name,
                "company_id": self.env.company.id,
                "list_price": price,
                "standard_price": price / 2,
                "taxes_id": [(6, 0, [self.company_data["default_tax_sale"].id])],
                "supplier_taxes_id": [
                    (6, 0, [self.company_data["default_tax_purchase"].id])
                ],
            }
        )
        return tmpl.product_variant_ids[0]

    def test_global_discount_split_proportional_to_invoice_subtotal(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente VE split desc",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345679",
            }
        )
        product_a = self._create_ve_product("Producto A", 1000.0)
        product_b = self._create_ve_product("Producto B", 100.0)
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product_a.id,
                            "product_uom_qty": 1,
                            "price_unit": 1000.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "product_id": product_b.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        },
                    ),
                ],
            }
        )
        wizard = self.env["sale.order.discount"].create(
            {
                "sale_order_id": order.id,
                "discount_type": "so_discount",
                "discount_percentage": 0.1,
            }
        )
        wizard.action_apply_discount()
        order.action_confirm()
        invoices = order._create_invoices()
        self.assertEqual(len(invoices), 2)
        discount_lines = invoices.invoice_line_ids.filtered(
            lambda aml: aml.product_id == order.company_id.sale_discount_product_id
        )
        self.assertEqual(len(discount_lines), 2)
        discount_amounts = sorted(abs(line.price_subtotal) for line in discount_lines)
        self.assertEqual(discount_amounts, [10.0, 100.0])
