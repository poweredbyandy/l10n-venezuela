# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestL10nVePayrollPayment(TransactionCase):
    """Payment must clear the 2103020 balance from the payslip move.

    Multicurrency rounds each move line; that sum can differ from rule TOTAL
    by Bs 0.01. Constants below are the exact company-currency amounts Odoo
    posts for the fixed USD inputs at EXCHANGE_RATE (not recomputed from TOTAL).
    """

    EXCHANGE_RATE = 859.063

    AMOUNT_BASIC_USD = 220.0
    AMOUNT_SSO_USD = 11.08
    AMOUNT_FAOV_USD = 2.2
    AMOUNT_RPE_USD = 1.38

    EXPECTED_BASIC_BS = 188993.86
    EXPECTED_SSO_BS = 9518.42
    EXPECTED_FAOV_BS = 1889.94
    EXPECTED_RPE_BS = 1185.51
    EXPECTED_PAYABLE_BS = 176399.99
    EXPECTED_TOTAL_LINE_BS = 176400.0

    def setUp(self):
        super().setUp()
        self.usd = self.env.ref("base.USD")
        self.ves = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "in", ("VES", "VEF"))], limit=1)
        )
        if not self.ves:
            self.ves = self.env["res.currency"].create(
                {"name": "VES", "symbol": "Bs.", "rounding": 0.01, "active": True}
            )
        else:
            self.ves.write({"active": True, "rounding": 0.01})

        self.company = self.env.company
        self.company.write(
            {
                "country_id": self.env.ref("base.ve").id,
                "currency_id": self.ves.id,
            }
        )

        today = fields.Date.today()
        rate = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.usd.id),
                ("name", "=", today),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        rate_vals = {"rate": 1.0 / self.EXCHANGE_RATE}
        if rate:
            rate.write(rate_vals)
        else:
            self.env["res.currency.rate"].create(
                {
                    "name": today,
                    "currency_id": self.usd.id,
                    "company_id": self.company.id,
                    **rate_vals,
                }
            )

        self.account_payable = self._ensure_account(
            "2103020",
            "NOMINA POR PAGAR",
            "liability_current",
            reconcile=True,
        )
        self.account_expense = self._ensure_account(
            "5102001",
            "SUELDOS Y SALARIOS",
            "expense",
        )
        self.account_sso = self._ensure_account(
            "2103003",
            "IVSS EMPLEADOS",
            "liability_current",
        )
        self.account_faov = self._ensure_account(
            "2103004",
            "FAOV EMPLEADOS",
            "liability_current",
        )
        self.account_rpe = self._ensure_account(
            "2103019",
            "RPE EMPLEADOS",
            "liability_current",
        )
        self.account_bank = self._ensure_account(
            "1111PAYT",
            "BANCO NOMINA TEST",
            "asset_cash",
        )
        self.journal_salary = self.env["account.journal"].create(
            {
                "name": "Salarios Test Pago",
                "code": "SLYP",
                "type": "general",
                "company_id": self.company.id,
                "default_account_id": self.account_expense.id,
            }
        )
        self.journal_bank = self.env["account.journal"].create(
            {
                "name": "Banco Nomina Test Pago",
                "code": "BNNP",
                "type": "bank",
                "company_id": self.company.id,
                "default_account_id": self.account_bank.id,
            }
        )

        Category = self.env["hr.salary.rule.category"]
        self.categ_basic = Category.create({"name": "Basic", "code": "BASIC_PAY"})
        self.categ_ded = Category.create({"name": "Deduction", "code": "DED_PAY"})
        self.categ_net = Category.create({"name": "Net", "code": "NET_PAY"})

        Rule = self.env["hr.salary.rule"]
        self.rule_basic = Rule.create(
            {
                "name": "Salario basico",
                "code": "SQUIN",
                "sequence": 1,
                "category_id": self.categ_basic.id,
                "condition_select": "none",
                "amount_select": "fix",
                "amount_fix": self.AMOUNT_BASIC_USD,
                "account_debit": self.account_expense.id,
                "account_credit": self.account_payable.id,
            }
        )
        self.rule_sso = Rule.create(
            {
                "name": "Retencion SSO",
                "code": "DESCSSO",
                "sequence": 100,
                "category_id": self.categ_ded.id,
                "condition_select": "none",
                "amount_select": "fix",
                "amount_fix": self.AMOUNT_SSO_USD,
                "account_debit": self.account_payable.id,
                "account_credit": self.account_sso.id,
            }
        )
        self.rule_faov = Rule.create(
            {
                "name": "Retencion FAOV",
                "code": "FAOV",
                "sequence": 101,
                "category_id": self.categ_ded.id,
                "condition_select": "none",
                "amount_select": "fix",
                "amount_fix": self.AMOUNT_FAOV_USD,
                "account_debit": self.account_payable.id,
                "account_credit": self.account_faov.id,
            }
        )
        self.rule_rpe = Rule.create(
            {
                "name": "Retencion RPE",
                "code": "RPE",
                "sequence": 102,
                "category_id": self.categ_ded.id,
                "condition_select": "none",
                "amount_select": "fix",
                "amount_fix": self.AMOUNT_RPE_USD,
                "account_debit": self.account_payable.id,
                "account_credit": self.account_rpe.id,
            }
        )
        self.rule_total = Rule.create(
            {
                "name": "Neto",
                "code": "TOTAL",
                "sequence": 200,
                "category_id": self.categ_net.id,
                "condition_select": "none",
                "amount_select": "code",
                "amount_python_compute": (
                    "result = categories.BASIC_PAY - categories.DED_PAY"
                ),
            }
        )

        self.structure = self.env["hr.payroll.structure"].create(
            {
                "name": "Test Quincenal Contable",
                "code": "TQCONT",
                "rule_ids": [
                    (
                        6,
                        0,
                        [
                            self.rule_basic.id,
                            self.rule_sso.id,
                            self.rule_faov.id,
                            self.rule_rpe.id,
                            self.rule_total.id,
                        ],
                    )
                ],
            }
        )

        self.employee = self.env["hr.employee"].create({"name": "Empleado Pago VE"})
        self.contract = self.env["hr.contract"].create(
            {
                "name": "Contrato Pago VE",
                "employee_id": self.employee.id,
                "wage": self.AMOUNT_BASIC_USD,
                "currency_id": self.usd.id,
                "struct_id": self.structure.id,
                "schedule_pay": "bi-weekly",
                "date_start": fields.Date.today() - relativedelta(years=1),
                "state": "open",
                "journal_id": self.journal_salary.id,
            }
        )

    def _ensure_account(self, code, name, account_type, reconcile=False):
        Account = self.env["account.account"]
        account = Account.search(
            [("code", "=", code), ("company_ids", "in", self.company.id)],
            limit=1,
        )
        if account:
            vals = {}
            if reconcile and not account.reconcile:
                vals["reconcile"] = True
            if vals:
                account.write(vals)
            return account
        return Account.create(
            {
                "name": name,
                "code": code,
                "account_type": account_type,
                "reconcile": reconcile,
                "company_ids": [(6, 0, [self.company.id])],
            }
        )

    def _create_payslip(self):
        return self.env["hr.payslip"].create(
            {
                "employee_id": self.employee.id,
                "contract_id": self.contract.id,
                "struct_id": self.structure.id,
                "date_from": fields.Date.today().replace(day=1),
                "date_to": fields.Date.today().replace(day=1) + relativedelta(days=14),
                "journal_id": self.journal_salary.id,
                "exchange_rate": self.EXCHANGE_RATE,
            }
        )

    def _payable_balance(self, move):
        lines = move.line_ids.filtered(
            lambda move_line: move_line.account_id == self.account_payable
        )
        return sum(lines.mapped("credit")) - sum(lines.mapped("debit"))

    def _account_balance(self, account, moves):
        lines = moves.line_ids.filtered(
            lambda move_line: move_line.account_id == account
        )
        return sum(lines.mapped("debit")) - sum(lines.mapped("credit"))

    def test_multicurrency_move_payable_differs_from_total_line(self):
        payslip = self._create_payslip()
        payslip.compute_sheet()

        line_basic = payslip.line_ids.filtered(lambda line: line.code == "SQUIN")
        line_sso = payslip.line_ids.filtered(lambda line: line.code == "DESCSSO")
        line_faov = payslip.line_ids.filtered(lambda line: line.code == "FAOV")
        line_rpe = payslip.line_ids.filtered(lambda line: line.code == "RPE")
        line_total = payslip.line_ids.filtered(lambda line: line.code == "TOTAL")

        self.assertEqual(line_basic.total, self.AMOUNT_BASIC_USD)
        self.assertEqual(line_sso.total, self.AMOUNT_SSO_USD)
        self.assertEqual(line_faov.total, self.AMOUNT_FAOV_USD)
        self.assertEqual(line_rpe.total, self.AMOUNT_RPE_USD)

        self.assertEqual(line_basic.total_company_currency, self.EXPECTED_BASIC_BS)
        self.assertEqual(line_sso.total_company_currency, self.EXPECTED_SSO_BS)
        self.assertEqual(line_faov.total_company_currency, self.EXPECTED_FAOV_BS)
        self.assertEqual(line_rpe.total_company_currency, self.EXPECTED_RPE_BS)
        self.assertEqual(line_total.total_company_currency, self.EXPECTED_TOTAL_LINE_BS)

        payslip.action_payslip_done()
        self.assertTrue(payslip.move_id)
        self.assertEqual(payslip.move_id.state, "posted")

        payable_balance = self._payable_balance(payslip.move_id)
        self.assertEqual(payable_balance, self.EXPECTED_PAYABLE_BS)
        self.assertNotEqual(
            payable_balance,
            line_total.total_company_currency,
            "Rounded move lines on 2103020 must expose the 0.01 drift vs TOTAL",
        )
        self.assertAlmostEqual(
            line_total.total_company_currency - payable_balance,
            0.01,
            places=2,
        )

        self.assertEqual(payslip.l10n_ve_amount_net, self.EXPECTED_PAYABLE_BS)
        self.assertEqual(payslip.l10n_ve_amount_residual, self.EXPECTED_PAYABLE_BS)
        self.assertEqual(payslip.l10n_ve_amount_paid, 0.0)

    def test_payment_clears_exact_payable_balance_not_total_line(self):
        payslip = self._create_payslip()
        payslip.compute_sheet()
        payslip.action_payslip_done()

        total_line_bs = payslip.line_ids.filtered(
            lambda line: line.code == "TOTAL"
        ).total_company_currency
        self.assertEqual(total_line_bs, self.EXPECTED_TOTAL_LINE_BS)
        self.assertEqual(payslip.l10n_ve_amount_residual, self.EXPECTED_PAYABLE_BS)

        wizard = (
            self.env["hr.payslip.payment.register"]
            .with_context(active_model="hr.payslip", active_ids=payslip.ids)
            .create(
                {
                    "journal_id": self.journal_bank.id,
                    "payment_date": fields.Date.today(),
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "payslip_id": payslip.id,
                                "amount": payslip.l10n_ve_amount_residual,
                            },
                        )
                    ],
                }
            )
        )
        self.assertEqual(wizard.line_ids.amount, self.EXPECTED_PAYABLE_BS)
        self.assertNotEqual(wizard.line_ids.amount, self.EXPECTED_TOTAL_LINE_BS)

        wizard.action_create_payments()
        payslip.invalidate_recordset()

        self.assertEqual(payslip.l10n_ve_amount_paid, self.EXPECTED_PAYABLE_BS)
        self.assertEqual(payslip.l10n_ve_amount_residual, 0.0)
        self.assertTrue(payslip.paid)
        self.assertEqual(len(payslip.l10n_ve_payment_move_ids), 1)

        accrual_and_payment = payslip.move_id | payslip.l10n_ve_payment_move_ids
        self.assertEqual(
            self._account_balance(self.account_payable, accrual_and_payment),
            0.0,
        )
        payment_bank_credit = sum(
            payslip.l10n_ve_payment_move_ids.line_ids.filtered(
                lambda move_line: move_line.account_id == self.account_bank
            ).mapped("credit")
        )
        self.assertEqual(payment_bank_credit, self.EXPECTED_PAYABLE_BS)

    def test_payment_default_rejects_total_line_drift(self):
        """Wizard defaults to payable balance; TOTAL is Bs 0.01 higher."""
        payslip = self._create_payslip()
        payslip.compute_sheet()
        payslip.action_payslip_done()

        wizard = (
            self.env["hr.payslip.payment.register"]
            .with_context(active_model="hr.payslip", active_ids=payslip.ids)
            .create({"journal_id": self.journal_bank.id})
        )
        self.assertEqual(wizard.line_ids.amount, self.EXPECTED_PAYABLE_BS)
        self.assertAlmostEqual(
            self.EXPECTED_TOTAL_LINE_BS - wizard.line_ids.amount,
            0.01,
            places=2,
        )
        self.assertGreater(
            self.EXPECTED_TOTAL_LINE_BS,
            payslip.l10n_ve_amount_residual,
        )
