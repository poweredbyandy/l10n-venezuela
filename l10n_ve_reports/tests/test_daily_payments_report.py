# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import tagged

from .common import TestAccountReportsCommon


@tagged("post_install", "-at_install")
class TestDailyPaymentsReport(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("l10n_ve_reports.daily_payments_report")
        cls.bank_journal = cls.company_data["default_journal_bank"]
        cls.bank_account = cls.bank_journal.default_account_id
        cls.counterpart_account = cls.company_data["default_account_revenue"]
        cls.deposit_move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": "2025-01-10",
                "journal_id": cls.bank_journal.id,
                "partner_id": cls.partner_a.id,
                "ref": "DEP-DAILY-001",
                "line_ids": [
                    Command.create(
                        {
                            "debit": 500.0,
                            "credit": 0.0,
                            "name": "Deposito en banco",
                            "account_id": cls.bank_account.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": 0.0,
                            "credit": 500.0,
                            "name": "Ingreso por deposito",
                            "account_id": cls.counterpart_account.id,
                        }
                    ),
                ],
            }
        )
        cls.deposit_move.action_post()

    def _get_report_lines(self, date_from="2025-01-01", date_to="2025-01-31"):
        options = self._generate_options(
            self.report,
            date_from,
            date_to,
            default_options={"unfold_all": True},
        )
        options = self._update_multi_selector_filter(
            options, "journals", self.bank_journal.ids
        )
        return self.report._get_lines(options), options

    def test_payment_method_children_use_hierarchical_ids(self):
        lines, _options = self._get_report_lines()
        method_lines = [
            line for line in lines if line.get("unfoldable") and line.get("level") == 2
        ]
        self.assertTrue(
            method_lines,
            "The report should expose unfoldable payment method lines",
        )
        for method_line in method_lines:
            children = [
                line
                for line in self.report._get_unfolded_lines(lines, method_line["id"])
                if line["id"] != method_line["id"]
            ]
            detail_lines = [line for line in children if line.get("level") == 4]
            self.assertTrue(
                detail_lines,
                "Unfolding a payment method should expose its payment lines",
            )
            for child in children:
                self.assertTrue(
                    child["id"].startswith(f"{method_line['id']}|"),
                    "Child line ids must keep the payment method id as prefix",
                )
                self.assertTrue(child.get("parent_id"))

    def test_daily_payments_caret_resolves_move_from_nested_line(self):
        lines, _options = self._get_report_lines()
        handler = self.env["account.daily.payments.report.handler.oca"]
        detail_lines = [
            line
            for line in lines
            if line.get("caret_options") == "account.move" and line.get("level") == 4
        ]
        self.assertTrue(detail_lines)
        move = handler._daily_payments_get_move_from_line_id(detail_lines[0]["id"])
        self.assertEqual(move, self.deposit_move)

    def _get_line_amount(self, line):
        return line["columns"][-1].get("no_format")

    def test_income_and_expense_are_shown_separately(self):
        outbound_method = self.bank_journal.outbound_payment_method_line_ids[:1]
        self.assertTrue(outbound_method)
        payment = self.env["account.payment"].create(
            {
                "amount": 150.0,
                "payment_type": "outbound",
                "partner_type": "supplier",
                "date": "2025-01-12",
                "journal_id": self.bank_journal.id,
                "partner_id": self.partner_a.id,
                "payment_method_line_id": outbound_method.id,
            }
        )
        payment.action_post()
        lines, _options = self._get_report_lines()

        def _named_lines(name, level):
            return [
                line
                for line in lines
                if line.get("name") == name and line.get("level") == level
            ]

        journal_income = _named_lines("Ingresos", 1)
        journal_expense = _named_lines("Egresos", 1)
        grand_total = _named_lines("Total", 0)
        self.assertTrue(journal_income)
        self.assertTrue(journal_expense)
        self.assertAlmostEqual(self._get_line_amount(journal_income[0]), 500.0)
        self.assertAlmostEqual(self._get_line_amount(journal_expense[0]), -150.0)
        self.assertAlmostEqual(self._get_line_amount(grand_total[0]), 350.0)
        income_methods = [
            line for line in lines if line.get("parent_id") == journal_income[0]["id"]
        ]
        expense_methods = [
            line for line in lines if line.get("parent_id") == journal_expense[0]["id"]
        ]
        self.assertTrue(
            any(line.get("name") == "Sin método de pago" for line in income_methods)
        )
        self.assertTrue(
            any(line.get("name") == outbound_method.name for line in expense_methods)
        )

    def _create_credit_invoice(self, move_type, amount, invoice_date="2025-01-15"):
        invoice = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner_a.id,
                "invoice_date": invoice_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Venta a credito",
                            "price_unit": amount,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def test_credit_invoices_are_listed_outside_grand_total(self):
        customer_invoice = self._create_credit_invoice("out_invoice", 300.0)
        vendor_bill = self._create_credit_invoice("in_invoice", 120.0)
        self._create_credit_invoice("out_invoice", 80.0, invoice_date="2025-02-10")
        lines, _options = self._get_report_lines()

        grand_total = [
            line
            for line in lines
            if line.get("name") == "Total" and line.get("level") == 0
        ]
        self.assertAlmostEqual(self._get_line_amount(grand_total[0]), 500.0)

        credit_methods = [
            line
            for line in lines
            if line.get("name") == "Crédito" and line.get("level") == 2
        ]
        self.assertEqual(len(credit_methods), 2)
        self.assertEqual(
            sorted(self._get_line_amount(line) for line in credit_methods),
            [-120.0, 300.0],
        )

        handler = self.env["account.daily.payments.report.handler.oca"]
        credit_moves = self.env["account.move"]
        for line in lines:
            if line.get("caret_options") == "daily_payments_credit_invoice":
                credit_moves |= handler._daily_payments_get_move_from_line_id(
                    line["id"]
                )
        self.assertEqual(credit_moves, customer_invoice | vendor_bill)

        credit_total = [line for line in lines if line.get("name") == "Total crédito"]
        self.assertAlmostEqual(self._get_line_amount(credit_total[0]), 180.0)

    def test_paid_invoices_are_not_listed_as_credit(self):
        invoice = self._create_credit_invoice("out_invoice", 200.0)
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({"payment_date": "2025-01-16"})._create_payments()
        lines, _options = self._get_report_lines()
        self.assertFalse(
            [
                line
                for line in lines
                if line.get("caret_options") == "daily_payments_credit_invoice"
            ]
        )
