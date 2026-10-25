# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def action_l10n_ve_register_payment(self):
        self.ensure_one()
        payslips = self.slip_ids.filtered(lambda slip: slip.state == "done")
        if not payslips:
            raise UserError(_("There are no confirmed payslips in this batch."))
        return payslips.action_l10n_ve_register_payment()
