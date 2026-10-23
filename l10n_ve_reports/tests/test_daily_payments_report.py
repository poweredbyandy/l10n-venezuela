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

    def _get_report_lines(
        self, date_from="2025-01-01", date_to="2025-01-31", extra_options=None
    ):
        default_options = {"unfold_all": True}
        if extra_options:
            default_options.update(extra_options)
        options = self._generate_options(
            self.report,
            date_from,
            date_to,
            default_options=default_options,
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
        self.assertTrue(
            any("o_daily_pay_bank" in (line.get("class") or "") for line in lines)
        )
        for line in lines:
            if line.get("name") in ("Ingresos", "Egresos") or "total" in (
                line.get("class") or ""
            ).split():
                self.assertNotIn("o_daily_pay_bank", line.get("class") or "")

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
        credit_header = [
            line for line in lines if line.get("name") == "Facturas a crédito"
        ]
        self.assertIn("o_daily_pay_credit", credit_header[0].get("class") or "")
        for line in lines:
            if line.get("name") in ("Ingresos", "Egresos") or "total" in (
                line.get("class") or ""
            ).split():
                self.assertNotIn("o_daily_pay_credit", line.get("class") or "")

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

    def _credit_invoice_lines(self, lines):
        return [
            line
            for line in lines
            if line.get("caret_options") == "daily_payments_credit_invoice"
        ]

    def _reconcile_partial_payment(self, invoice, amount, is_retention):
        journal = self.env["account.journal"].create(
            {
                "name": "Diario retencion pagos",
                "type": "bank",
                "code": "RTDP" if is_retention else "PYDP",
                "company_id": invoice.company_id.id,
            }
        )
        payment_type = (
            "inbound"
            if invoice.is_sale_document(include_receipts=True)
            else "outbound"
        )
        method_lines = (
            journal.inbound_payment_method_line_ids
            if payment_type == "inbound"
            else journal.outbound_payment_method_line_ids
        )
        payment = self.env["account.payment"].create(
            {
                "amount": amount,
                "payment_type": payment_type,
                "partner_type": "customer" if payment_type == "inbound" else "supplier",
                "date": "2025-01-16",
                "journal_id": journal.id,
                "partner_id": invoice.partner_id.id,
                "payment_method_line_id": method_lines[:1].id,
                "is_retention": is_retention,
            }
        )
        payment.action_post()
        account_type = (
            "asset_receivable"
            if invoice.is_sale_document(include_receipts=True)
            else "liability_payable"
        )
        lines = (invoice | payment.move_id).line_ids.filtered(
            lambda line: line.account_id.account_type == account_type
            and not line.reconciled
        )
        lines.reconcile()
        return payment

    def test_retention_partial_keeps_full_amount_as_credit(self):
        invoice = self._create_credit_invoice("out_invoice", 200.0)
        self._reconcile_partial_payment(invoice, 16.0, is_retention=True)
        self.assertEqual(invoice.payment_state, "partial")
        self.assertAlmostEqual(invoice.amount_residual, 184.0)

        lines, _options = self._get_report_lines()
        credit_lines = self._credit_invoice_lines(lines)
        self.assertEqual(len(credit_lines), 1)
        self.assertAlmostEqual(self._get_line_amount(credit_lines[0]), 200.0)

        grand_total = [
            line
            for line in lines
            if line.get("name") == "Total" and line.get("level") == 0
        ]
        self.assertAlmostEqual(self._get_line_amount(grand_total[0]), 500.0)

    def test_real_partial_payment_reduces_credit_amount(self):
        invoice = self._create_credit_invoice("out_invoice", 200.0)
        self._reconcile_partial_payment(invoice, 16.0, is_retention=True)
        self._reconcile_partial_payment(invoice, 50.0, is_retention=False)
        self.assertEqual(invoice.payment_state, "partial")

        lines, _options = self._get_report_lines()
        credit_lines = self._credit_invoice_lines(lines)
        self.assertEqual(len(credit_lines), 1)
        self.assertAlmostEqual(self._get_line_amount(credit_lines[0]), 150.0)

    def _create_terminal_closing(self, amounts, payment_date, deposit_date, ref):
        method = self.bank_journal.inbound_payment_method_line_ids[:1]
        self.assertTrue(method)
        payments = self.env["account.payment"].create(
            [
                {
                    "amount": amount,
                    "payment_type": "inbound",
                    "partner_type": "customer",
                    "date": payment_date,
                    "journal_id": self.bank_journal.id,
                    "partner_id": self.partner_a.id,
                    "payment_method_line_id": method.id,
                }
                for amount in amounts
            ]
        )
        payments.action_post()
        outstanding = payments.outstanding_account_id
        liquidity = payments.move_id.line_ids.filtered(
            lambda line: line.account_id == outstanding and not line.reconciled
        )
        total = sum(amounts)
        closing_move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": deposit_date,
                "journal_id": self.bank_journal.id,
                "ref": ref,
                "line_ids": [
                    Command.create(
                        {
                            "name": "Pago agrupado",
                            "account_id": outstanding.id,
                            "debit": 0.0,
                            "credit": amount,
                        }
                    )
                    for amount in amounts
                ]
                + [
                    Command.create(
                        {
                            "name": ref,
                            "account_id": outstanding.id,
                            "debit": total,
                            "credit": 0.0,
                        }
                    )
                ],
            }
        )
        closing_move.action_post()
        counterparts = closing_move.line_ids.filtered(lambda line: line.credit)
        (liquidity | counterparts).reconcile()
        return payments, closing_move, method

    def test_closing_shows_detailed_payments(self):
        payments, _closing_move, method = self._create_terminal_closing(
            (250.0, 150.0), "2025-01-12", "2025-01-12", "CIERRE/0001"
        )
        lines, _options = self._get_report_lines()
        self.assertFalse([line for line in lines if line.get("name") == "CIERRE/0001"])
        detail_lines = [
            line
            for line in lines
            if line.get("name") in payments.move_id.mapped("name")
        ]
        self.assertEqual(len(detail_lines), 2)
        self.assertEqual(
            sorted(self._get_line_amount(line) for line in detail_lines),
            [150.0, 250.0],
        )
        income = [
            line
            for line in lines
            if line.get("name") == "Ingresos" and line.get("level") == 1
        ]
        self.assertAlmostEqual(self._get_line_amount(income[0]), 900.0)
        method_lines = [line for line in lines if line.get("name") == method.name]
        self.assertTrue(method_lines)
        self.assertAlmostEqual(self._get_line_amount(method_lines[0]), 400.0)

    def test_closing_details_follow_payment_date_not_deposit(self):
        payments, closing_move, method = self._create_terminal_closing(
            (250.0, 150.0), "2025-01-12", "2025-01-13", "CIERRE/0002"
        )
        lines_payment_day, _options = self._get_report_lines(
            date_from="2025-01-12",
            date_to="2025-01-12",
            extra_options={"daily_payments_date_type": "payment"},
        )
        detail_lines = [
            line
            for line in lines_payment_day
            if line.get("name") in payments.move_id.mapped("name")
        ]
        self.assertEqual(len(detail_lines), 2)
        self.assertEqual(
            sorted(self._get_line_amount(line) for line in detail_lines),
            [150.0, 250.0],
        )
        self.assertFalse(
            [line for line in lines_payment_day if line.get("name") == "CIERRE/0002"]
        )
        method_lines = [
            line for line in lines_payment_day if line.get("name") == method.name
        ]
        self.assertAlmostEqual(self._get_line_amount(method_lines[0]), 400.0)

        lines_deposit_day, _options = self._get_report_lines(
            date_from="2025-01-13",
            date_to="2025-01-13",
            extra_options={"daily_payments_date_type": "payment"},
        )
        self.assertFalse(
            [
                line
                for line in lines_deposit_day
                if line.get("name") in payments.move_id.mapped("name")
            ]
        )
        self.assertFalse(
            [line for line in lines_deposit_day if line.get("name") == closing_move.ref]
        )

    def test_credit_invoices_can_be_hidden(self):
        self._create_credit_invoice("out_invoice", 300.0)
        lines, options = self._get_report_lines(
            extra_options={"daily_payments_show_credit_invoices": False}
        )
        self.assertFalse(options["daily_payments_show_credit_invoices"])
        self.assertFalse(self._credit_invoice_lines(lines))
        self.assertFalse([line for line in lines if line.get("name") == "Total crédito"])
        grand_total = [
            line
            for line in lines
            if line.get("name") == "Total" and line.get("level") == 0
        ]
        self.assertAlmostEqual(self._get_line_amount(grand_total[0]), 500.0)
