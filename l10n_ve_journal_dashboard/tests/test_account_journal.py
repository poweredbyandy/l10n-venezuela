# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestL10nVeJournalDashboard(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.change_company_country(cls.env.company, cls.env.ref("base.ve"))
        cls.today = fields.Date.today()
        cls.AccountJournal = cls.env["account.journal"]

    def _l10n_ve_create_posted_move(self, move_type, **values):
        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner_a.id,
                "journal_id": self.company_data["default_journal_sale"].id,
                "invoice_date": self.today,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": move_type,
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
                **values,
            }
        )
        move.action_post()
        return move

    def test_invoice_dashboard_counts_current_month(self):
        month_start = self.today.replace(day=1)
        invoice = self._l10n_ve_create_posted_move("out_invoice")
        self._l10n_ve_create_posted_move("out_refund", reversed_entry_id=invoice.id)

        data = self.AccountJournal.get_l10n_ve_invoice_dashboard()
        self.assertTrue(data["visible"])
        counts = {item["key"]: item["count"] for item in data["items"]}
        self.assertGreaterEqual(counts["posted_invoices_month"], 1)
        self.assertGreaterEqual(counts["credit_notes_month"], 1)

        invoice_action = self.AccountJournal.action_l10n_ve_invoice_dashboard_open(
            "posted_invoices_month"
        )
        self.assertEqual(invoice_action["res_model"], "account.move")
        self.assertIn(("invoice_date", ">=", month_start), invoice_action["domain"])
        self.assertIn(("move_type", "=", "out_invoice"), invoice_action["domain"])

        credit_action = self.AccountJournal.action_l10n_ve_invoice_dashboard_open(
            "credit_notes_month"
        )
        self.assertIn(("move_type", "=", "out_refund"), credit_action["domain"])

    def test_invoice_dashboard_counts_overdue_unpaid_invoices(self):
        invoice = self._l10n_ve_create_posted_move(
            "out_invoice",
            invoice_date=self.today - relativedelta(days=10),
            invoice_date_due=self.today - relativedelta(days=5),
        )
        self.assertIn(invoice.payment_state, ("not_paid", "partial"))

        data = self.AccountJournal.get_l10n_ve_invoice_dashboard()
        counts = {item["key"]: item["count"] for item in data["items"]}
        self.assertGreaterEqual(counts["overdue_unpaid_invoices"], 1)

        action = self.AccountJournal.action_l10n_ve_invoice_dashboard_open(
            "overdue_unpaid_invoices"
        )
        self.assertIn(("move_type", "=", "out_invoice"), action["domain"])
        self.assertIn(
            ("payment_state", "in", ("not_paid", "partial")), action["domain"]
        )
        self.assertIn(("invoice_date_due", "<", self.today), action["domain"])

    def test_invoice_dashboard_hidden_for_non_ve_company(self):
        self.change_company_country(self.env.company, self.env.ref("base.us"))
        data = self.AccountJournal.get_l10n_ve_invoice_dashboard()
        self.assertFalse(data["visible"])
