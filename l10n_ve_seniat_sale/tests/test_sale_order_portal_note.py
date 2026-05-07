# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestSaleOrderPortalNoteVe(L10nVeSeniatCommon):
    def test_l10n_ve_seniat_note_includes_igtf_when_taxpayer_not_ordinary(self):
        self.env.company.partner_id.taxpayer_type = "formal"
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente portal VE",
                "country_id": self.env.ref("base.ve").id,
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Prod portal",
                "list_price": 10.0,
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 10.0,
                        },
                    )
                ],
            }
        )
        self.assertTrue(order.l10n_ve_seniat_note)
        self.assertIn("IGTF", order.l10n_ve_seniat_note)

    def test_l10n_ve_seniat_note_false_when_ordinary_taxpayer_only_igtf_branch(self):
        self.env.company.partner_id.taxpayer_type = "ordinary"
        partner = self.env["res.partner"].create(
            {
                "name": "Cliente ordinario",
                "country_id": self.env.ref("base.ve").id,
            }
        )
        product = self.env["product.product"].create(
            {
                "name": "Prod ord",
                "list_price": 5.0,
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                            "price_unit": 5.0,
                        },
                    )
                ],
            }
        )
        self.assertFalse(order.l10n_ve_seniat_note)
