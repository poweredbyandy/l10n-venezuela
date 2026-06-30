# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged
from lxml import etree

from .test_stock_picking_dispatch_guide import TestL10nVeStockDispatchGuide


@tagged("post_install", "-at_install")
class TestL10nVeStockPickingReports(TestL10nVeStockDispatchGuide):
    def test_only_dispatch_guide_bound_to_stock_picking(self):
        picking_model = self.env["ir.model"]._get("stock.picking")
        dispatch_report = self.env.ref(
            "l10n_ve_stock.action_report_l10n_ve_dispatch_guide"
        )
        bound_reports = self.env["ir.actions.report"].search(
            [
                ("binding_model_id", "=", picking_model.id),
                ("binding_type", "=", "report"),
            ]
        )
        self.assertEqual(bound_reports, dispatch_report)

    def test_ve_outgoing_picking_only_allows_dispatch_guide_report(self):
        product = self._create_product(
            name="Prod reportes",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self._button_validate_through_wizards(picking)
        report_model = self.env["ir.actions.report"]
        bound_reports = report_model.search(
            [
                ("model", "=", "stock.picking"),
                ("report_type", "=", "qweb-pdf"),
                ("binding_model_id.model", "=", "stock.picking"),
            ]
        )
        domain_reports = bound_reports.filtered("domain")
        valid_ids = domain_reports.get_valid_action_reports(
            "stock.picking", picking.ids
        )
        dispatch_report = self.env.ref(
            "l10n_ve_stock.action_report_l10n_ve_dispatch_guide"
        )
        self.assertIn(dispatch_report.id, valid_ids)
        blocked = domain_reports.filtered(
            lambda report: report.id in valid_ids
            and report.id != dispatch_report.id
        )
        self.assertFalse(blocked)

    def test_dispatch_guide_not_in_print_actions_before_delivery_done(self):
        product = self._create_product(
            name="Prod acciones print",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        dispatch_report = self.env.ref(
            "l10n_ve_stock.action_report_l10n_ve_dispatch_guide"
        )
        valid_ids = dispatch_report.get_valid_action_reports(
            "stock.picking", picking.ids
        )
        self.assertNotIn(dispatch_report.id, valid_ids)
        self.assertFalse(picking._l10n_ve_dispatch_guide_print_available())

    def test_do_print_picking_prints_dispatch_guide_for_ve_outgoing(self):
        product = self._create_product(
            name="Prod print btn",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self._button_validate_through_wizards(picking)
        self.assertEqual(picking.state, "done")
        action = picking.do_print_picking()
        self.assertEqual(
            action.get("report_name"),
            "l10n_ve_stock.report_dispatch_guide",
        )

    def test_do_print_picking_uses_standard_report_when_dispatch_disabled(self):
        self.env.company.l10n_ve_dispatch_guide_enabled = False
        product = self._create_product(
            name="Prod print estándar",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        picking.move_ids.quantity = picking.move_ids.product_uom_qty
        picking.move_ids.picked = True
        picking.button_validate()
        action = picking.do_print_picking()
        self.assertEqual(action.get("report_name"), "stock.report_picking")

    def test_portal_picking_control_number_display(self):
        product = self._create_product(
            name="Prod portal label",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self._button_validate_through_wizards(picking)
        self.assertTrue(picking.l10n_ve_control_number)
        self.assertEqual(
            picking.l10n_ve_portal_control_number_display(),
            picking.l10n_ve_control_number,
        )

    def test_portal_template_shows_control_number(self):
        product = self._create_product(
            name="Prod portal qweb",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        order = self._prepare_outgoing_sale_picking(product, 1).sale_id
        picking = order.picking_ids.filtered(
            lambda p: p.picking_type_id.code == "outgoing"
        )[:1]
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self._button_validate_through_wizards(picking)
        combined_arch = self.env.ref(
            "sale.sale_order_portal_content"
        )._get_combined_arch()
        arch_text = etree.tostring(combined_arch, encoding="unicode")
        self.assertIn("l10n_ve_portal_control_number_display", arch_text)
        self.assertNotIn("l10n_ve_portal_dispatch_guides", arch_text)
        from odoo.tools import is_html_empty

        html = self.env["ir.qweb"]._render(
            "sale.sale_order_portal_content",
            {
                "sale_order": order,
                "report_type": "html",
                "product_documents": order._get_product_documents(),
                "is_html_empty": is_html_empty,
            },
        )
        html_text = html.decode() if isinstance(html, bytes) else str(html)
        self.assertIn(picking.l10n_ve_control_number, html_text)
        self.assertIn("N° de control:", html_text)
        self.assertIn("Last Delivery Orders", html_text)

    def test_portal_invoice_control_number_on_invoices_only(self):
        product = self._create_product(
            name="Prod portal facturado",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        product.invoice_policy = "order"
        picking = self._prepare_outgoing_sale_picking(product, 1)
        invoice = picking.sale_id._create_invoices()
        invoice.action_post()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        self._button_validate_through_wizards(picking)
        self.assertFalse((picking.l10n_ve_control_number or "").strip())
        self.assertFalse(picking.l10n_ve_portal_control_number_display())
        self.assertEqual(
            invoice.l10n_ve_portal_control_number_display(),
            invoice.l10n_ve_control_number,
        )
        from odoo.tools import is_html_empty

        html = self.env["ir.qweb"]._render(
            "sale.sale_order_portal_content",
            {
                "sale_order": picking.sale_id,
                "report_type": "html",
                "product_documents": picking.sale_id._get_product_documents(),
                "is_html_empty": is_html_empty,
            },
        )
        html_text = html.decode() if isinstance(html, bytes) else str(html)
        self.assertIn(invoice.l10n_ve_control_number, html_text)
        invoice_idx = html_text.find("Last Invoices")
        delivery_idx = html_text.find("Last Delivery Orders")
        self.assertGreater(invoice_idx, -1)
        self.assertGreater(delivery_idx, -1)
        self.assertLess(invoice_idx, delivery_idx)
        invoice_block = html_text[invoice_idx:delivery_idx]
        delivery_block = html_text[delivery_idx:delivery_idx + 1000]
        self.assertIn(invoice.l10n_ve_control_number, invoice_block)
        self.assertNotIn("N° de control", delivery_block)

    def test_dispatch_guide_print_blocked_before_delivery_done(self):
        product = self._create_product(
            name="Prod print bloqueado",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        picking = self._prepare_outgoing_sale_picking(product, 1)
        with self.assertRaises(UserError):
            picking.do_print_picking()

    def test_internal_picking_has_no_print_reports(self):
        picking_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "internal"),
                ("company_id", "=", self.env.company.id),
            ],
            limit=1,
        )
        self.assertTrue(picking_type)
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
            }
        )
        report_model = self.env["ir.actions.report"]
        domain_reports = report_model.search(
            [
                ("model", "=", "stock.picking"),
                ("report_type", "=", "qweb-pdf"),
                ("binding_model_id.model", "=", "stock.picking"),
                ("domain", "!=", False),
            ]
        )
        valid_ids = domain_reports.get_valid_action_reports(
            "stock.picking", picking.ids
        )
        self.assertEqual(valid_ids, [])

    def test_extra_picking_report_is_unbound_on_create(self):
        picking_model = self.env["ir.model"]._get("stock.picking")
        extra_report = self.env["ir.actions.report"].create(
            {
                "name": "Reporte extra test",
                "model": "stock.picking",
                "report_type": "qweb-pdf",
                "report_name": "l10n_ve_stock.report_extra_test",
                "binding_model_id": picking_model.id,
                "binding_type": "report",
            }
        )
        dispatch_report = self.env.ref(
            "l10n_ve_stock.action_report_l10n_ve_dispatch_guide"
        )
        self.assertFalse(extra_report.binding_model_id)
        bound_reports = self.env["ir.actions.report"].search(
            [
                ("binding_model_id", "=", picking_model.id),
                ("binding_type", "=", "report"),
            ]
        )
        self.assertEqual(bound_reports, dispatch_report)

    def test_dispatch_guide_shows_company_header_without_control_number(self):
        product = self._create_product(name="Prod header guía", is_storable=True)
        product.invoice_policy = "order"
        picking = self._prepare_outgoing_sale_picking(product, 1)
        invoice = picking.sale_id._create_invoices()
        invoice.action_post()
        self.assertFalse((picking.l10n_ve_control_number or "").strip())
        self.assertTrue(picking._l10n_ve_dispatch_guide_shows_company_header())

    def test_dispatch_guide_hides_company_header_with_control_number(self):
        picking = self._create_ve_sale_and_validate_delivery()
        self.assertTrue(picking.l10n_ve_control_number)
        self.assertFalse(picking._l10n_ve_dispatch_guide_shows_company_header())

    def test_dispatch_guide_paperformat_letter_when_no_talonario(self):
        product = self._create_product(
            name="Prod formato guía",
            is_storable=True,
            taxes_id=[Command.set(self.tax_sale_a.ids)],
        )
        product.invoice_policy = "order"
        picking = self._prepare_outgoing_sale_picking(product, 1)
        invoice = picking.sale_id._create_invoices()
        invoice.action_post()
        paperformat = picking._l10n_ve_dispatch_guide_paperformat()
        letter_format = self.env.ref(
            "l10n_ve_stock.paperformat_l10n_ve_dispatch_guide_letter"
        )
        self.assertEqual(paperformat, letter_format)
        self.assertEqual(paperformat.format, "Letter")
        self.assertEqual(paperformat.margin_top, 7)

    def test_dispatch_guide_paperformat_uses_book_when_has_talonario(self):
        picking = self._create_ve_sale_and_validate_delivery()
        section = picking._l10n_ve_dispatch_guide_section()
        self.assertTrue(section)
        book = section.book_id
        book._l10n_ve_ensure_paperformat()
        self.assertTrue(book.paperformat_id)
        paperformat = picking._l10n_ve_dispatch_guide_paperformat()
        self.assertEqual(paperformat, book.paperformat_id)
        self.assertNotEqual(
            paperformat,
            self.env.ref("l10n_ve_stock.paperformat_l10n_ve_dispatch_guide_letter"),
        )
