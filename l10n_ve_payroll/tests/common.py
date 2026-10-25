# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.payroll.tests.common import TestPayslipBase


@tagged("post_install", "-at_install")
class TestL10nVePayrollCommon(TestPayslipBase):
    """Company in VES; contracts may use USD/EUR (not RT company-USD dual)."""

    EXCHANGE_RATE = 627.34
    WAGE_USD = 1000.0

    def setUp(self):
        super().setUp()
        self.env.user.tz = "America/Caracas"
        self.usd = self.env.ref("base.USD")
        self.eur = self.env.ref("base.EUR")
        self.ves = (
            self.env["res.currency"]
            .with_context(active_test=False)
            .search([("name", "=", "VES")], limit=1)
        )
        if not self.ves:
            self.ves = (
                self.env["res.currency"]
                .with_context(active_test=False)
                .search([("name", "=", "VEF")], limit=1)
            )
        if not self.ves:
            self.ves = self.env["res.currency"].create(
                {"name": "VES", "symbol": "Bs.", "rounding": 0.01, "active": True}
            )
        else:
            self.ves.active = True

        self.company = self.env.company
        self.company.write(
            {
                "country_id": self.env.ref("base.ve").id,
                "currency_id": self.ves.id,
                "minimum_wage": 130.00,
                "sso_employee_rate": 4.0,
                "sso_employer_risk_rate": 10.0,
                "faov_employee_rate": 1.0,
                "faov_employer_rate": 2.0,
                "rpe_employee_rate": 0.5,
                "rpe_employer_rate": 2.0,
                "inces_employer_rate": 2.0,
                "inces_min_employees": 5,
                "cepp_employer_rate": 9.0,
                "profit_sharing_days": 30,
                "meal_ticket_amount": 40.0,
            }
        )
        today = fields.Date.today()
        existing = self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", self.usd.id),
                ("name", "=", today),
                ("company_id", "=", self.company.id),
            ],
            limit=1,
        )
        if existing:
            existing.rate = 1.0 / self.EXCHANGE_RATE
        else:
            self.env["res.currency.rate"].create(
                {
                    "name": today,
                    "currency_id": self.usd.id,
                    "company_id": self.company.id,
                    "rate": 1.0 / self.EXCHANGE_RATE,
                }
            )

        self.struct_biweekly = self.env.ref("l10n_ve_payroll.structure_quincenal")
        self.struct_weekly = self.env.ref("l10n_ve_payroll.structure_semanal")
        self.struct_meal = self.env.ref("l10n_ve_payroll.structure_alimentacion")
        self.struct_leave = self.env.ref("l10n_ve_payroll.structure_vacaciones")
        self.struct_profit = self.env.ref("l10n_ve_payroll.structure_utilidades")
        self.struct_severance = self.env.ref("l10n_ve_payroll.structure_liquidacion")

        self.richard_contract.write(
            {
                "currency_id": self.usd.id,
                "wage": self.WAGE_USD,
                "struct_id": self.struct_biweekly.id,
                "schedule_pay": "bi-weekly",
                "withhold_sso": True,
                "withhold_faov": True,
                "withhold_rpe": True,
                "profit_sharing_days": 30,
            }
        )

    def _create_ve_payslip(self, employee=None, contract=None, structure=None):
        employee = employee or self.richard_emp
        contract = contract or self.richard_contract
        structure = structure or contract.struct_id
        return self.Payslip.create(
            {
                "employee_id": employee.id,
                "contract_id": contract.id,
                "struct_id": structure.id,
                "date_from": fields.Date.today().replace(day=1),
                "date_to": fields.Date.today().replace(day=1)
                + relativedelta(days=14),
                "exchange_rate": self.EXCHANGE_RATE,
            }
        )

    def _assert_company_currency_line(self, payslip, code):
        line = payslip.line_ids.filtered(lambda item: item.code == code)
        self.assertTrue(line, "Expected payslip line with code %s" % code)
        self.assertAlmostEqual(
            line.total_company_currency,
            line.total * self.EXCHANGE_RATE,
            places=2,
        )
        return line
