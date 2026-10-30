# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestPostedCatalog(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_foreign = cls.env["res.partner"].create(
            {
                "name": "Partner extranjero catálogo",
                "country_id": cls.env.ref("base.us").id,
            }
        )
        cls.product_catalog = cls._create_product(
            name="Estopera de prueba",
            lst_price=30.0,
        )

    def _draft_invoice(self):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_foreign.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product_a.id,
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [(6, 0, self.product_a.taxes_id.ids)],
                        },
                    )
                ],
            }
        )

    def test_catalog_adds_product_while_draft(self):
        move = self._draft_invoice()
        self.assertFalse(move._is_readonly())
        move._update_order_line_info(self.product_catalog.id, 1)
        self.assertIn(self.product_catalog, move.invoice_line_ids.product_id)

    def test_catalog_rejects_product_after_post_from_another_session(self):
        move = self._draft_invoice()
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertTrue(move._is_readonly())
        product_lines = move.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )

        with self.assertRaises(UserError):
            move._update_order_line_info(self.product_catalog.id, 1)
        with self.assertRaises(UserError):
            move._update_order_line_info(self.product_a.id, 5)
        with self.assertRaises(UserError):
            self.env["account.move.line"].create(
                {
                    "move_id": move.id,
                    "product_id": self.product_catalog.id,
                    "quantity": 1.0,
                }
            )

        self.assertEqual(
            move.invoice_line_ids.filtered(
                lambda line: line.display_type == "product"
            ),
            product_lines,
        )
        self.assertEqual(
            product_lines.filtered(lambda line: line.product_id == self.product_a).quantity,
            1.0,
        )
