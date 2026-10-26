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

    def _set_commission_account(self, account):
        config = self.env["l10n_ve.default.account"].search(
            [("company_id", "=", self.company.id)], limit=1
        )
        if config:
            config.commission_account_id = account
        elif account:
            self.env["l10n_ve.default.account"].create(
                {
                    "company_id": self.company.id,
                    "commission_account_id": account.id,
                }
            )

    def test_commission_keyword_ignores_accents(self):
        lines = self.env["account.bank.statement.line"].create(
            [
                {
                    "date": "2026-09-01",
                    "journal_id": self.bank_journal.id,
                    "payment_ref": "COMISIÓN PUNTO DE VENTA",
                    "amount": -12.5,
                },
                {
                    "date": "2026-09-01",
                    "journal_id": self.bank_journal.id,
                    "payment_ref": "comisiones mantenimiento",
                    "amount": -3.0,
                },
                {
                    "date": "2026-09-01",
                    "journal_id": self.bank_journal.id,
                    "payment_ref": "Pago cliente 1234",
                    "amount": 40.0,
                },
            ]
        )
        self.assertTrue(lines[0]._is_bank_commission_line())
        self.assertTrue(lines[1]._is_bank_commission_line())
        self.assertFalse(lines[2]._is_bank_commission_line())

    def test_commission_line_posts_to_expense_account(self):
        expense = self.company_data["default_account_expense"]
        self._set_commission_account(expense)
        line = self.env["account.bank.statement.line"].create(
            {
                "date": "2026-09-02",
                "journal_id": self.bank_journal.id,
                "payment_ref": "COMISION POS BNC",
                "amount": -18.0,
            }
        )
        with patch.object(
            type(line), "_reconcile_by_bank_reference", return_value=True
        ) as reference_mock:
            self.assertTrue(line._reconcile_bank_commission())
            reference_mock.assert_not_called()
        self.assertTrue(line.is_reconciled)
        commission_lines = line.move_id.line_ids.filtered(
            lambda aml: aml.account_id == expense
        )
        self.assertEqual(len(commission_lines), 1)
        self.assertEqual(commission_lines.balance, 18.0)
        rule = self.env["account.reconcile.model"].search(
            [
                ("company_id", "=", self.company.id),
                ("name", "=", "VE: Comisión bancaria"),
            ]
        )
        self.assertEqual(len(rule), 1)
        self.assertFalse(rule.auto_reconcile)

    def test_commission_without_account_stays_open(self):
        self._set_commission_account(False)
        line = self.env["account.bank.statement.line"].create(
            {
                "date": "2026-09-03",
                "journal_id": self.bank_journal.id,
                "payment_ref": "COMISION MANTENIMIENTO",
                "amount": -4.0,
            }
        )
        self.assertFalse(line._reconcile_bank_commission())
        self.assertFalse(line.is_reconciled)

    def _post_terminal_closing(self, amount, date="2026-09-10", deposit_date=None):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": amount,
                "date": date,
                "journal_id": self.bank_journal.id,
            }
        )
        payment.action_post()
        closing = self.env["account.payment.closing"].create(
            {
                "journal_id": self.bank_journal.id,
                "date": date,
                "deposit_date": deposit_date or date,
            }
        )
        closing.action_search_payments()
        closing.action_post()
        return closing

    def _pos_deposit_line(self, amount, date="2026-09-10"):
        return self.env["account.bank.statement.line"].create(
            {
                "date": date,
                "journal_id": self.bank_journal.id,
                "payment_ref": "ABONO PUNTO DE VENTA",
                "amount": amount,
            }
        )

    def test_posted_terminal_closing_matches_the_deposit(self):
        closing = self._post_terminal_closing(400.0)
        line = self._pos_deposit_line(400.0)
        self.assertTrue(line._reconcile_pos_income())
        self.assertTrue(line.is_reconciled)
        self.assertTrue(closing.is_matched)

    def test_draft_terminal_closing_is_ignored(self):
        payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 80.0,
                "date": "2026-09-10",
                "journal_id": self.bank_journal.id,
            }
        )
        payment.action_post()
        closing = self.env["account.payment.closing"].create(
            {
                "journal_id": self.bank_journal.id,
                "date": "2026-09-10",
            }
        )
        closing.action_search_payments()
        line = self._pos_deposit_line(80.0)
        self.assertFalse(line._reconcile_pos_income())
        self.assertEqual(closing.state, "draft")
        self.assertFalse(line.is_reconciled)

    def test_two_closings_with_the_same_amount_stay_open(self):
        self._post_terminal_closing(150.0)
        self._post_terminal_closing(150.0)
        line = self._pos_deposit_line(150.0)
        self.assertFalse(line._reconcile_pos_income())
        self.assertFalse(line.is_reconciled)

    def test_deposit_on_another_date_stays_open(self):
        self._post_terminal_closing(90.0, deposit_date="2026-09-11")
        line = self._pos_deposit_line(90.0, date="2026-09-10")
        self.assertFalse(line._reconcile_pos_income())
        self.assertFalse(line.is_reconciled)
