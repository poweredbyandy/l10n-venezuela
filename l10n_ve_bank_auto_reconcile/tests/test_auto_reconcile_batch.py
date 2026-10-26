# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_ve_bank_auto_reconcile.models import (
    account_bank_statement_line as batch_model,
)


@tagged("post_install", "-at_install")
class TestAutoReconcileBatch(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data["default_journal_bank"]

    def _create_lines(self, count):
        return self.env["account.bank.statement.line"].create(
            [
                {
                    "date": "2026-09-01",
                    "journal_id": self.bank_journal.id,
                    "payment_ref": "ref-%s" % index,
                    "amount": 10.0 + index,
                }
                for index in range(count)
            ]
        )

    def _jobs(self):
        return self.env["queue.job"].search(
            [
                (
                    "identity_key",
                    "=",
                    "l10n_ve_bank_auto_reconcile:%s" % self.company.id,
                )
            ]
        )

    def test_cron_stays_inactive(self):
        cron = self.env.ref("account_accountant.auto_reconcile_bank_statement_line")
        self.assertFalse(cron.active)

    def test_button_enqueues_without_calling_cron(self):
        lines = self._create_lines(3)
        statement_line = self.env["account.bank.statement.line"]
        with patch.object(
            type(statement_line),
            "_cron_try_auto_reconcile_statement_lines",
        ) as cron_mock:
            action = lines.action_queue_ref_auto_reconcile()
        cron_mock.assert_not_called()
        self.assertEqual(action["tag"], "display_notification")
        jobs = self._jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs.channel, "root")
        self.assertEqual(list(jobs.args[0]), lines.sorted(key=lambda line: (line.date, line.id)).ids)

    def test_second_click_is_rejected_while_job_is_pending(self):
        lines = self._create_lines(2)
        lines.action_queue_ref_auto_reconcile()
        with self.assertRaises(UserError):
            lines.action_queue_ref_auto_reconcile()

    def test_batch_stops_at_25_lines_and_queues_the_rest(self):
        lines = self._create_lines(26)
        ordered_ids = lines.sorted(key=lambda line: (line.date, line.id)).ids
        with patch.object(
            type(lines), "_reconcile_by_bank_reference", return_value=False
        ):
            result = lines.job_reconcile_reference_batch(ordered_ids, self.company.id)
        self.assertEqual(result["processed"], 25)
        self.assertEqual(result["remaining"], 1)
        jobs = self._jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(list(jobs.args[0]), [ordered_ids[-1]])

    def test_batch_stops_when_thirty_seconds_elapse(self):
        lines = self._create_lines(5)
        ordered_ids = lines.sorted(key=lambda line: (line.date, line.id)).ids
        with (
            patch.object(type(lines), "_reconcile_by_bank_reference", return_value=False),
            patch.object(batch_model.time, "monotonic", side_effect=[0, 10, 40]),
        ):
            result = lines.job_reconcile_reference_batch(ordered_ids, self.company.id)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["remaining"], 4)

    def test_button_without_journal_raises(self):
        with self.assertRaises(UserError):
            self.env["account.bank.statement.line"].with_context(
                default_journal_id=False,
                search_default_journal_id=False,
            ).action_queue_ref_auto_reconcile()
