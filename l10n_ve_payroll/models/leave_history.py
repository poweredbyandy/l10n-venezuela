# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class L10nVePayrollLeaveHistory(models.Model):
    _name = "l10n_ve.payroll.leave.history"
    _description = "Venezuelan Leave History"
    _order = "year desc, id desc"

    employee_id = fields.Many2one("hr.employee", required=True, index=True)
    year = fields.Integer(required=True)
    days_earned = fields.Float(default=0.0)
    days_taken = fields.Float(default=0.0)
    days_balance = fields.Float(compute="_compute_days_balance", store=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company
    )
    source_payslip_id = fields.Many2one("hr.payslip")

    @api.depends("days_earned", "days_taken")
    def _compute_days_balance(self):
        for record in self:
            record.days_balance = record.days_earned - record.days_taken
