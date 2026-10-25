# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrRuleParameter(models.Model):
    """Lightweight dated legal parameters (BW-inspired) when payroll has no core model.

    If upstream OCA payroll later ships hr.rule.parameter, replace this with inherit.
    """

    _name = "l10n_ve.payroll.rule.parameter"
    _description = "Venezuelan Payroll Rule Parameter"
    _order = "date_from desc, id desc"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    date_from = fields.Date(required=True)
    parameter_value = fields.Char(required=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company
    )
