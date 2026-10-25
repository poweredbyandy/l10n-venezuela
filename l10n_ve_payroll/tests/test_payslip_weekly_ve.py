# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import TestL10nVePayrollCommon


@tagged("post_install", "-at_install")
class TestPayslipWeeklyVe(TestL10nVePayrollCommon):
    def test_compute_sheet_company_ves_contract_usd(self):
        self.assertEqual(self.company.currency_id, self.ves)
        self.assertEqual(self.richard_contract.currency_id, self.usd)
        self.richard_contract.write(
            {
                "struct_id": self.struct_weekly.id,
                "schedule_pay": "weekly",
            }
        )
        payslip = self._create_ve_payslip(structure=self.struct_weekly)
        payslip.compute_sheet()
        self.assertTrue(payslip.line_ids)
        self.assertAlmostEqual(payslip.exchange_rate, self.EXCHANGE_RATE, places=4)
        self._assert_company_currency_line(payslip, "SSEMA")
        self._assert_company_currency_line(payslip, "TOTAL")
