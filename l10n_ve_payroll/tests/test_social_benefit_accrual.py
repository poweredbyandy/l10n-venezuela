# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import TestL10nVePayrollCommon


@tagged("post_install", "-at_install")
class TestSocialBenefitAccrual(TestL10nVePayrollCommon):
    def test_force_social_benefit_on_done(self):
        payslip = self._create_ve_payslip()
        payslip.compute_sheet()
        payslip.with_context(
            l10n_ve_force_social_benefit=True
        )._l10n_ve_process_social_benefits()
        self.assertTrue(payslip.social_benefit_id)
        self.assertEqual(payslip.social_benefit_id.employee_id, self.richard_emp)
        benefit = payslip.social_benefit_id
        payslip.social_benefit_id = False
        self.env.cr.execute(
            "DELETE FROM l10n_ve_payroll_social_benefit WHERE id = %s",
            (benefit.id,),
        )
        benefit.invalidate_recordset()
        self.assertFalse(benefit.exists())
