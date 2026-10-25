# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class PayrollEmployeeLoan(models.Model):
    _inherit = "payroll.employee.loan"

    def _get_disbursement_account(self):
        self.ensure_one()
        account = super()._get_disbursement_account()
        if account:
            return account
        return self.company_id.loan_receivable_account_id
