# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.tests import tagged

from .common import TestAccountReportsCommon


@tagged("post_install", "-at_install")
class TestAgedPartnerDocumentLabel(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.receivable_report = cls.env.ref("l10n_ve_reports.aged_receivable_report")
        cls.payable_report = cls.env.ref("l10n_ve_reports.aged_payable_report")

    def _document_line_names(self, report, date):
        options = self._generate_options(
            report, date, date, default_options={"unfold_all": True}
        )
        lines = report._get_lines(options)
        return [line["name"] for line in lines]

    def test_receivable_shows_invoice_name_and_control_number(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": fields.Date.from_string("2025-03-10"),
                "l10n_ve_control_number": "00-00001234",
                "l10n_ve_invoice_number": "000987",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Servicio",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        names = self._document_line_names(self.receivable_report, "2025-03-10")
        self.assertIn("000987 / 00-00001234", names)

    def test_payable_shows_vendor_invoice_and_control_number(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": fields.Date.from_string("2025-03-12"),
                "date": fields.Date.from_string("2025-03-12"),
                "ref": "F-8841",
                "l10n_ve_control_number": "00-00009999",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Compra",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [],
                        }
                    )
                ],
            }
        )
        bill.action_post()
        names = self._document_line_names(self.payable_report, "2025-03-12")
        self.assertIn("F-8841 / 00-00009999", names)
