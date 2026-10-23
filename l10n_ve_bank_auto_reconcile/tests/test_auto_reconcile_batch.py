# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_ve_bank_auto_reconcile.models import (
    l10n_ve_bank_reconcile_queue as batch_model,
)


@tagged("post_install", "-at_install")
class TestAutoReconcileBatch(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.queue = cls.env["l10n.ve.bank.reconcile.queue"]

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

    def _queue_entries(self):
        return self.queue.search([("company_id", "=", self.company.id)])

    def test_accountant_cron_stays_inactive(self):
        cron = self.env.ref("account_accountant.auto_reconcile_bank_statement_line")
        self.assertFalse(cron.active)

    def test_button_enqueues_without_calling_accountant_cron(self):
        lines = self._create_lines(3)
        statement_line = self.env["account.bank.statement.line"]
        with patch.object(
            type(statement_line),
            "_cron_try_auto_reconcile_statement_lines",
        ) as cron_mock:
            action = lines.action_queue_ref_auto_reconcile()
        cron_mock.assert_not_called()
        self.assertEqual(action["tag"], "display_notification")
        entries = self._queue_entries()
        ordered = lines.sorted(key=lambda line: (line.date, line.id))
        self.assertEqual(entries.statement_line_id, ordered)

    def test_second_click_runs_cron_when_lines_are_already_queued(self):
        lines = self._create_lines(2)
        lines.action_queue_ref_auto_reconcile()
        with patch.object(type(self.queue), "_cron_process_queue") as cron_mock:
            action = lines.action_queue_ref_auto_reconcile()
        cron_mock.assert_called_once()
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(len(self._queue_entries()), 2)

    def test_batch_stops_at_limit_and_keeps_the_rest(self):
        limit = batch_model.BATCH_LINE_LIMIT
        lines = self._create_lines(limit + 1)
        lines.action_queue_ref_auto_reconcile()
        with patch.object(
            type(lines), "_reconcile_by_bank_reference", return_value=False
        ):
            result = self.queue._process_company_batch(self.company)
        self.assertEqual(result["processed"], limit)
        self.assertEqual(result["remaining"], 1)
        entries = self._queue_entries()
        ordered_ids = lines.sorted(key=lambda line: (line.date, line.id)).ids
        self.assertEqual(entries.statement_line_id.ids, [ordered_ids[-1]])

    def test_failed_reconcile_still_removes_queue_entry(self):
        lines = self._create_lines(1)
        lines.action_queue_ref_auto_reconcile()
        self.assertEqual(len(self._queue_entries()), 1)
        with patch.object(
            type(lines), "_reconcile_by_bank_reference", return_value=False
        ):
            self.queue._process_company_batch(self.company)
        self.assertEqual(len(self._queue_entries()), 0)
        self.assertFalse(lines.is_reconciled)
        queued = self.env["account.bank.statement.line"].search(
            [("in_auto_reconcile_queue", "=", True)]
        )
        self.assertFalse(queued)

    def test_batch_stops_when_thirty_seconds_elapse(self):
        lines = self._create_lines(5)
        lines.action_queue_ref_auto_reconcile()
        with (
            patch.object(type(lines), "_reconcile_by_bank_reference", return_value=False),
            patch.object(batch_model.time, "monotonic", side_effect=[0, 10, 40]),
        ):
            result = self.queue._process_company_batch(self.company)
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["remaining"], 4)

    def test_queue_lists_only_pending_lines_of_the_open_bank(self):
        lines = self._create_lines(2)
        other_journal = self.bank_journal.copy({"name": "Other bank", "code": "BNK2"})
        other_lines = self.env["account.bank.statement.line"].create(
            [
                {
                    "date": "2026-09-02",
                    "journal_id": other_journal.id,
                    "payment_ref": "other",
                    "amount": 5.0,
                }
            ]
        )
        (lines | other_lines).action_queue_ref_auto_reconcile()
        action = self.env["account.bank.statement.line"].with_context(
            default_journal_id=self.bank_journal.id
        ).action_open_reference_reconcile_queue()
        self.assertEqual(action["res_model"], "l10n.ve.bank.reconcile.queue")
        entries = self.queue.search(action["domain"])
        self.assertEqual(set(entries.statement_line_id.ids), set(lines.ids))
        queued = self.env["account.bank.statement.line"].search(
            [("in_auto_reconcile_queue", "=", True)]
        )
        self.assertEqual(set(queued.ids), set((lines | other_lines).ids))

    def test_open_queue_is_empty_without_entries(self):
        action = (
            self.env["account.bank.statement.line"].action_open_reference_reconcile_queue()
        )
        self.assertEqual(action["domain"], [("id", "in", [])])

    def test_button_without_journal_raises(self):
        with self.assertRaises(UserError):
            self.env["account.bank.statement.line"].with_context(
                default_journal_id=False,
                search_default_journal_id=False,
            ).action_queue_ref_auto_reconcile()
