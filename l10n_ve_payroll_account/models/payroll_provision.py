# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class L10nVePayrollProvision(models.Model):
    """Phase-2 accounting provision (BW-inspired). MVP model stub."""

    _name = "l10n_ve.payroll.provision"
    _description = "Venezuelan Payroll Provision"
    _order = "date desc, id desc"

    name = fields.Char(required=True)
    date = fields.Date(required=True, default=fields.Date.context_today)
    employee_id = fields.Many2one("hr.employee")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    provision_type = fields.Selection(
        [
            ("profit_sharing", "Profit Sharing"),
            ("leave", "Leave"),
            ("meal", "Meal Allowance"),
            ("social_benefit", "Social Benefit"),
        ],
        required=True,
    )
    amount = fields.Monetary(currency_field="currency_id")
    move_id = fields.Many2one("account.move", copy=False)
    state = fields.Selection(
        [("draft", "Draft"), ("posted", "Posted"), ("cancelled", "Cancelled")],
        default="draft",
    )
