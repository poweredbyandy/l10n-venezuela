# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestPaymentClosing(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.closing_date = "2026-10-14"
        cls.payments = cls._create_payments([100.0, 250.0, 50.0])
        cls.other_day_payment = cls._create_payments([75.0], date="2026-10-15")

    @classmethod
    def _create_payments(cls, amounts, date=None, payment_type="inbound"):
        payments = cls.env["account.payment"].create(
            [
                {
                    "payment_type": payment_type,
                    "partner_type": "customer",
                    "partner_id": cls.partner_a.id,
                    "amount": amount,
                    "date": date or cls.closing_date,
                    "journal_id": cls.bank_journal.id,
                }
                for amount in amounts
            ]
        )
        payments.action_post()
        return payments

    def _create_closing(self):
        return self.env["account.payment.closing"].create(
            {
                "journal_id": self.bank_journal.id,
                "date": self.closing_date,
            }
        )

    def test_search_payments_of_the_day(self):
        closing = self._create_closing()
        closing.action_search_payments()
        self.assertEqual(closing.payment_ids, self.payments)
        self.assertEqual(closing.amount_total, 400.0)
        self.assertNotIn(self.other_day_payment, closing.payment_ids)

    def test_post_creates_single_open_line(self):
        closing = self._create_closing()
        closing.action_search_payments()
        closing.action_post()
        self.assertEqual(closing.state, "posted")
        self.assertNotEqual(closing.name, "/")
        self.assertEqual(closing.move_id.state, "posted")
        open_lines = closing.move_id.line_ids.filtered(lambda line: not line.reconciled)
        self.assertEqual(open_lines, closing.closing_line_id)
        self.assertEqual(closing.closing_line_id.amount_residual, 400.0)
        self.assertEqual(
            closing.closing_line_id.account_id,
            self.payments.outstanding_account_id,
        )
        self.assertTrue(all(self.payments.mapped("is_matched")))
        self.assertFalse(closing.is_matched)

    def test_matched_closing_cannot_be_reset(self):
        closing = self._create_closing()
        closing.action_search_payments()
        closing.action_post()
        bank_move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": self.bank_journal.id,
                "date": self.closing_date,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "account_id": self.bank_journal.default_account_id.id,
                            "debit": 400.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "account_id": closing.outstanding_account_id.id,
                            "credit": 400.0,
                        },
                    ),
                ],
            }
        )
        bank_move.action_post()
        (
            bank_move.line_ids.filtered(
                lambda line: line.account_id == closing.outstanding_account_id
            )
            | closing.closing_line_id
        ).reconcile()
        self.assertTrue(closing.is_matched)
        with self.assertRaises(UserError):
            closing.action_draft()

    def test_entry_uses_bank_credit_date(self):
        closing = self._create_closing()
        self.assertEqual(str(closing.deposit_date), self.closing_date)
        closing.deposit_date = "2026-10-15"
        closing.action_search_payments()
        self.assertEqual(closing.payment_ids, self.payments)
        closing.action_post()
        self.assertEqual(str(closing.move_id.date), "2026-10-15")
        self.assertEqual(str(closing.closing_line_id.date), "2026-10-15")

    def test_bank_credit_date_before_closing_date(self):
        closing = self._create_closing()
        with self.assertRaises(ValidationError):
            closing.deposit_date = "2026-10-13"

    def test_payment_in_closing_is_not_searched_again(self):
        closing = self._create_closing()
        closing.action_search_payments()
        closing.action_post()
        other_closing = self._create_closing()
        with self.assertRaises(UserError):
            other_closing.action_search_payments()

    def test_refund_reduces_total(self):
        refund = self._create_payments([30.0], payment_type="outbound")
        closing = self._create_closing()
        closing.action_search_payments()
        self.assertIn(refund, closing.payment_ids)
        self.assertEqual(closing.amount_total, 370.0)
        self.assertEqual(
            closing.outstanding_account_id, self.payments.outstanding_account_id
        )
        closing.action_post()
        open_lines = closing.move_id.line_ids.filtered(lambda line: not line.reconciled)
        self.assertEqual(open_lines, closing.closing_line_id)
        self.assertEqual(closing.closing_line_id.amount_residual, 370.0)
        self.assertTrue(refund.is_matched)

    def test_reset_to_draft_releases_payments(self):
        closing = self._create_closing()
        closing.action_search_payments()
        closing.action_post()
        move = closing.move_id
        closing.action_draft()
        self.assertEqual(closing.state, "draft")
        self.assertEqual(move.state, "cancel")
        self.assertFalse(closing.closing_line_id)
        self.assertFalse(any(self.payments.mapped("is_matched")))

    def test_payment_in_posted_closing_cannot_be_reset(self):
        closing = self._create_closing()
        closing.action_search_payments()
        closing.action_post()
        with self.assertRaises(UserError):
            self.payments[0].action_draft()

    def test_remove_payment_from_draft_closing(self):
        closing = self._create_closing()
        closing.action_search_payments()
        self.payments[0].action_remove_from_closing()
        self.assertEqual(closing.payment_ids, self.payments[1:])
        self.assertEqual(closing.amount_total, 300.0)

    def test_filter_by_payment_method(self):
        terminal_line = self.env["account.payment.method.line"].create(
            {
                "name": "Terminal 2",
                "payment_method_id": self.env.ref(
                    "account.account_payment_method_manual_in"
                ).id,
                "journal_id": self.bank_journal.id,
            }
        )
        terminal_payment = self.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner_a.id,
                "amount": 20.0,
                "date": self.closing_date,
                "journal_id": self.bank_journal.id,
                "payment_method_line_id": terminal_line.id,
            }
        )
        terminal_payment.action_post()
        closing = self._create_closing()
        closing.payment_method_line_ids = terminal_line
        closing.action_search_payments()
        self.assertEqual(closing.payment_ids, terminal_payment)
