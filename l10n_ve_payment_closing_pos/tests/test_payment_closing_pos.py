# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestPaymentClosingPos(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.closing_date = "2026-10-14"
        cls.terminal_a, cls.terminal_b = cls.env["pos.payment.method"].create(
            [
                {"name": "Terminal A", "journal_id": cls.bank_journal.id},
                {"name": "Terminal B", "journal_id": cls.bank_journal.id},
            ]
        )
        cls.payment_a = cls._create_pos_payment(cls.terminal_a, 300.0)
        cls.payment_b = cls._create_pos_payment(cls.terminal_b, 120.0)

    @classmethod
    def _create_pos_payment(cls, pos_method, amount):
        payment = cls.env["account.payment"].create(
            {
                "payment_type": "inbound",
                "partner_type": "customer",
                "amount": amount,
                "date": cls.closing_date,
                "journal_id": cls.bank_journal.id,
                "pos_payment_method_id": pos_method.id,
            }
        )
        payment.action_post()
        return payment

    def test_filter_by_pos_payment_method(self):
        closing = self.env["account.payment.closing"].create(
            {
                "journal_id": self.bank_journal.id,
                "date": self.closing_date,
                "pos_payment_method_ids": [(6, 0, self.terminal_a.ids)],
            }
        )
        closing.action_search_payments()
        self.assertEqual(closing.payment_ids, self.payment_a)
        closing.action_post()
        self.assertEqual(closing.closing_line_id.amount_residual, 300.0)
        self.assertFalse(self.payment_b.closing_id)
