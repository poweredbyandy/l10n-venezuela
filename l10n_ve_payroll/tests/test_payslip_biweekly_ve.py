# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import TestL10nVePayrollCommon


@tagged("post_install", "-at_install")
class TestPayslipBiweeklyVe(TestL10nVePayrollCommon):
    def test_compute_sheet_company_ves_contract_usd(self):
        self.assertEqual(self.company.currency_id, self.ves)
        self.assertEqual(self.richard_contract.currency_id, self.usd)
        payslip = self._create_ve_payslip(structure=self.struct_biweekly)
        payslip.compute_sheet()
        self.assertTrue(payslip.line_ids)
        self.assertAlmostEqual(payslip.exchange_rate, self.EXCHANGE_RATE, places=4)
        self.assertTrue(payslip.period_mondays >= 1)
        self._assert_company_currency_line(payslip, "SQUIN")
        self._assert_company_currency_line(payslip, "TOTAL")
