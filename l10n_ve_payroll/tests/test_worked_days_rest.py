# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import tagged

from .common import TestL10nVePayrollCommon


@tagged("post_install", "-at_install")
class TestWorkedDaysRestVe(TestL10nVePayrollCommon):
    def _prepare_september_contract(self):
        """2026-09-01..15: Mon-Fri work days=11, Sat=2, Sun=2."""
        date_from = fields.Date.to_date("2026-09-01")
        date_to = fields.Date.to_date("2026-09-15")
        calendar = self.env.ref(
            "l10n_ve_payroll.resource_calendar_ve_diurna_40h",
            raise_if_not_found=False,
        )
        vals = {
            "date_start": fields.Date.to_date("2026-01-01"),
            "date_end": False,
            "struct_id": self.struct_biweekly.id,
            "wage": self.WAGE_USD,
            "currency_id": self.usd.id,
            "schedule_pay": "bi-weekly",
        }
        if calendar:
            vals["resource_calendar_id"] = calendar.id
            self.richard_emp.resource_calendar_id = calendar
            if not calendar.l10n_ve_paid_rest_day_ids:
                calendar.write(
                    {
                        "l10n_ve_paid_rest_day_ids": [
                            (
                                0,
                                0,
                                {
                                    "name": "Saturday rest days",
                                    "dayofweek": "5",
                                    "code": "DDESS",
                                    "sequence": 2,
                                },
                            ),
                            (
                                0,
                                0,
                                {
                                    "name": "Sunday rest days",
                                    "dayofweek": "6",
                                    "code": "DDESD",
                                    "sequence": 3,
                                },
                            ),
                        ]
                    }
                )
        self.richard_contract.write(vals)
        return date_from, date_to

    def test_get_worked_day_lines_adds_saturday_and_sunday(self):
        date_from, date_to = self._prepare_september_contract()
        lines = self.Payslip.get_worked_day_lines(
            self.richard_contract, date_from, date_to
        )
        by_code = {line["code"]: line for line in lines}

        self.assertIn("WORK100", by_code)
        self.assertEqual(by_code["WORK100"]["number_of_days"], 11.0)
        self.assertIn("DDESS", by_code)
        self.assertEqual(by_code["DDESS"]["number_of_days"], 2.0)
        self.assertIn("DDESD", by_code)
        self.assertEqual(by_code["DDESD"]["number_of_days"], 2.0)

        expected_rest_pay = (self.WAGE_USD / 30.0) * 2.0
        self.assertAlmostEqual(expected_rest_pay, 66.6666666667, places=4)

    def test_onchange_loads_rest_days_on_payslip(self):
        date_from, date_to = self._prepare_september_contract()
        payslip = self.Payslip.new(
            {
                "employee_id": self.richard_emp.id,
                "contract_id": self.richard_contract.id,
                "struct_id": self.struct_biweekly.id,
                "date_from": date_from,
                "date_to": date_to,
                "exchange_rate": self.EXCHANGE_RATE,
            }
        )
        payslip.onchange_employee()
        ddess = payslip.worked_days_line_ids.filtered(lambda line: line.code == "DDESS")
        ddesd = payslip.worked_days_line_ids.filtered(lambda line: line.code == "DDESD")
        work100 = payslip.worked_days_line_ids.filtered(
            lambda line: line.code == "WORK100"
        )
        self.assertEqual(sum(work100.mapped("number_of_days")), 11.0)
        self.assertEqual(sum(ddess.mapped("number_of_days")), 2.0)
        self.assertEqual(sum(ddesd.mapped("number_of_days")), 2.0)
