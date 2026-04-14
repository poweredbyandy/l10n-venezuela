from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged

from odoo.addons.sale_stock.tests.common import TestSaleStockCommon


@tagged("post_install", "-at_install")
class TestL10nVeStockDispatchGuide(TestSaleStockCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write(
            {"account_fiscal_country_id": cls.env.ref("base.ve").id}
        )
        cls._setup_l10n_ve_dispatch_section()

    @classmethod
    def _setup_l10n_ve_dispatch_section(cls):
        company = cls.env.company
        book = cls.env["account.book"].create(
            {
                "name": "Talonario guías test",
                "company_id": company.id,
                "number_from": 1,
                "number_to": 99_999_999,
                "l10n_ve_series_prefix": "01",
            }
        )
        sec = cls.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "Guías despacho",
                "number_from": 40_000_000,
                "number_to": 49_999_999,
            }
        )
        warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        warehouse.l10n_ve_dispatch_guide_section_id = sec

    def _create_ve_sale_and_validate_delivery(self):
        product = self._create_product(
            name="Prod guía despacho",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                        }
                    )
                ],
            }
        )
        so.action_confirm()
        picking = so.picking_ids.filtered(
            lambda p: p.picking_type_id.code == "outgoing" and p.state != "done"
        )
        self.assertTrue(len(picking) >= 1)
        picking = picking[0]
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking._action_done()
        return picking

    def test_outgoing_sale_picking_gets_control_number_when_not_invoiced(self):
        picking = self._create_ve_sale_and_validate_delivery()
        self.assertTrue(picking.l10n_ve_control_number)
        self.assertRegex(picking.l10n_ve_control_number, r"^01-\d{8}$")
        doc = self.env["account.book.document"].search(
            [
                ("res_model", "=", "stock.picking"),
                ("res_id", "=", picking.id),
            ]
        )
        self.assertEqual(len(doc), 1)

    def test_no_control_number_without_dispatch_section(self):
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        wh.l10n_ve_dispatch_guide_section_id = False
        picking = self._create_ve_sale_and_validate_delivery()
        self.assertFalse((picking.l10n_ve_control_number or "").strip())

    def test_section_other_company_raises(self):
        company_b = self.env["res.company"].create({"name": "Empresa B VE guía"})
        book_b = self.env["account.book"].create(
            {
                "name": "Talonario B",
                "company_id": company_b.id,
                "number_from": 1,
                "number_to": 99_999_999,
            }
        )
        sec_b = self.env["account.book.section"].create(
            {
                "book_id": book_b.id,
                "name": "Guías B",
                "number_from": 1,
                "number_to": 9_999_999,
            }
        )
        wh = self.env["stock.warehouse"].search(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        wh.l10n_ve_dispatch_guide_section_id = sec_b
        with self.assertRaises(ValidationError):
            self._create_ve_sale_and_validate_delivery()

    def test_picking_invoice_ids_synced_from_sale_invoice(self):
        picking = self._create_ve_sale_and_validate_delivery()
        so = picking.sale_id
        invoice = so._create_invoices()
        self.assertTrue(picking.invoice_ids)
        self.assertIn(invoice, picking.invoice_ids)
        self.assertEqual(invoice.picking_ids, picking)

    def test_backorder_outgoing_gets_control_after_partial_delivery_and_invoice(self):
        product = self._create_product(
            name="Prod guía entrega parcial",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        product.invoice_policy = "delivery"
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 10,
                        }
                    )
                ],
            }
        )
        so.action_confirm()
        picking = so.picking_ids.filtered(
            lambda p: p.picking_type_id.code == "outgoing" and p.state != "done"
        )[:1]
        self.assertTrue(picking)
        picking.action_assign()
        picking.move_ids.quantity = 5
        picking.move_ids.picked = True
        action = picking.button_validate()
        self.assertIsInstance(action, dict)
        wiz = Form(
            self.env["stock.backorder.confirmation"].with_context(**action["context"])
        ).save()
        wiz.process()
        pick1 = so.picking_ids.filtered(
            lambda p: p.picking_type_id.code == "outgoing" and p.state == "done"
        )
        self.assertEqual(len(pick1), 1)
        pick1 = pick1[0]
        self.assertTrue(pick1.l10n_ve_control_number)
        invoice = so._create_invoices()
        self.assertTrue(invoice)
        invoice.action_post()
        pick2 = so.picking_ids.filtered(
            lambda p: p.picking_type_id.code == "outgoing" and p.state != "done"
        )[:1]
        self.assertTrue(pick2)
        pick2.action_assign()
        pick2.move_ids.quantity = pick2.move_ids.product_uom_qty
        pick2.move_ids.picked = True
        pick2._action_done()
        self.assertTrue(pick2.l10n_ve_control_number)
        self.assertNotEqual(
            pick2.l10n_ve_control_number,
            pick1.l10n_ve_control_number,
        )

    def test_no_control_number_when_fully_invoiced_before_delivery(self):
        product = self._create_product(
            name="Prod factura antes entrega",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        product.invoice_policy = "order"
        so = self.env["sale.order"].create(
            {
                "partner_id": self.partner_a.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": 1,
                        }
                    )
                ],
            }
        )
        so.action_confirm()
        invoice = so._create_invoices()
        invoice.action_post()
        picking = so.picking_ids.filtered(
            lambda p: p.picking_type_id.code == "outgoing" and p.state != "done"
        )[:1]
        self.assertTrue(picking)
        picking.action_assign()
        picking.move_ids.quantity = picking.move_ids.product_uom_qty
        picking.move_ids.picked = True
        picking._action_done()
        self.assertFalse((picking.l10n_ve_control_number or "").strip())
