# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeJournalDashboardEdi(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountJournal = cls.env["account.journal"]

    def test_unsent_dashboard_hidden_without_digital_provider(self):
        self.AccountJournal.search(
            [("company_id", "=", self.env.company.id), ("type", "=", "sale")]
        ).write({"l10n_ve_edi_provider": "none"})
        data = self.AccountJournal.get_l10n_ve_edi_unsent_dashboard()
        self.assertFalse(data["visible"])
        self.assertEqual(data["items"], [])

    def test_unsent_dashboard_open_returns_filtered_actions(self):
        invoice_action = self.AccountJournal.action_l10n_ve_edi_unsent_dashboard_open(
            "unsent_invoices"
        )
        self.assertEqual(invoice_action["res_model"], "account.move")
        self.assertEqual(invoice_action["domain"][0][:2], ("id", "in"))

        retention_action = self.AccountJournal.action_l10n_ve_edi_unsent_dashboard_open(
            "unsent_retentions"
        )
        self.assertEqual(retention_action["res_model"], "account.retention")

    def test_unsent_dashboard_open_rejects_unknown_key(self):
        with self.assertRaises(UserError):
            self.AccountJournal.action_l10n_ve_edi_unsent_dashboard_open("unknown")
