from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import new_test_user

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestL10nVeStockProductFiscalLocks(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write(
            {"account_fiscal_country_id": cls.env.ref("base.ve").id}
        )
        if not cls.tax_sale_b:
            cls.tax_sale_b = cls.tax_sale_a.copy({"name": "sale_tax_b_dup"})

    def test_product_requires_exactly_one_sale_tax_ve(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create(
                {
                    "name": "Sin impuesto",
                    "is_storable": True,
                    "taxes_id": [Command.clear()],
                }
            )
        with self.assertRaises(ValidationError):
            self.env["product.template"].create(
                {
                    "name": "Dos impuestos",
                    "is_storable": True,
                    "taxes_id": [
                        Command.set((self.tax_sale_a + self.tax_sale_b).ids)
                    ],
                }
            )

    def test_product_default_code_and_taxes_locked_after_done_move(self):
        product = self._create_product(
            name="Prod bloqueo",
            is_storable=True,
            default_code="REF-001",
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        tmpl = product.product_tmpl_id
        picking_type_in = self.env["stock.picking.type"].search(
            [
                ("code", "=", "incoming"),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        self.assertTrue(picking_type_in)
        supplier_loc = self.env.ref("stock.stock_location_suppliers")
        stock_loc = picking_type_in.default_location_dest_id
        picking_in = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type_in.id,
                "location_id": supplier_loc.id,
                "location_dest_id": stock_loc.id,
            }
        )
        move = self.env["stock.move"].create(
            {
                "name": product.name,
                "product_id": product.id,
                "product_uom_qty": 1,
                "product_uom": product.uom_id.id,
                "picking_id": picking_in.id,
                "location_id": supplier_loc.id,
                "location_dest_id": stock_loc.id,
            }
        )
        picking_in.action_confirm()
        picking_in.action_assign()
        move.move_line_ids.quantity = 1
        move.move_line_ids.picked = True
        picking_in._action_done()

        user = new_test_user(
            self.env,
            login="l10n_ve_stock_lock_user",
            groups="stock.group_stock_manager",
        )
        self.assertFalse(
            user.has_group("l10n_ve_seniat.group_l10n_ve_override_locked_master_data")
        )
        tmpl_as_user = tmpl.with_user(user)
        with self.assertRaises(UserError):
            tmpl_as_user.write({"default_code": "REF-002"})
        with self.assertRaises(UserError):
            tmpl_as_user.write({"taxes_id": [Command.set(self.tax_sale_b.ids)]})

        tmpl.write(
            {
                "default_code": "REF-ADM",
                "taxes_id": [Command.set(self.tax_sale_b.ids)],
            }
        )
        self.assertEqual(tmpl.default_code, "REF-ADM")
        self.assertEqual(tmpl.taxes_id, self.tax_sale_b)
