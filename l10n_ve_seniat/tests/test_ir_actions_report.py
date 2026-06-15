# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestIrActionsReport(L10nVeSeniatCommon):
    def test_render_qweb_pdf_marks_original_printed(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Partner",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        move.action_post()
        report = self.env.ref("account.account_invoices", raise_if_not_found=False)
        if report:
            report.with_context(l10n_ve_invoice=True)._render_qweb_pdf(
                report.report_name, move.ids
            )
            move.invalidate_recordset()
            self.assertTrue(move.l10n_ve_invoice_original_printed)
            self.assertTrue(move.invoice_pdf_report_id)

    def test_invoice_report_uses_book_paperformat(self):
        book = self.env["account.book"].search(
            [("name", "=", "Talonario tests")], limit=1
        )
        self.assertTrue(book.paperformat_id)
        book.write({"l10n_ve_invoice_header_spacing": 42})
        book.paperformat_id.invalidate_recordset()
        self.assertEqual(book.paperformat_id.header_spacing, 42)

        partner = self.env["res.partner"].create(
            {
                "name": "Partner PF",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345679",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        move.action_post()
        self.assertEqual(move._l10n_ve_get_invoice_paperformat(), book.paperformat_id)

        report = self.env.ref("account.account_invoices", raise_if_not_found=False)
        if report:
            report = report.with_context(
                l10n_ve_book_paperformat_id=book.paperformat_id.id
            )
            self.assertEqual(report.get_paperformat(), book.paperformat_id)

    def test_get_valid_action_reports_hides_invoice_pdf_for_draft(self):
        report = self.env.ref(
            "account.account_invoices_without_payment", raise_if_not_found=False
        )
        if not report:
            return
        partner = self.env["res.partner"].create(
            {
                "name": "Partner Draft",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J12345680",
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "invoice_date": fields.Date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )
        report = report.with_context(l10n_ve_skip_server_action_unbind=True)
        report.write({"binding_model_id": self.env["ir.model"]._get("account.move").id})
        valid_ids = report.get_valid_action_reports("account.move", move.ids)
        self.assertNotIn(report.id, valid_ids)
        move.action_post()
        self._mark_invoice_printed(move)
        valid_ids = report.get_valid_action_reports("account.move", move.ids)
        self.assertIn(report.id, valid_ids)
