# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    minimum_wage = fields.Monetary(
        related="company_id.minimum_wage",
        readonly=False,
        currency_field="currency_id",
    )
    sso_employee_rate = fields.Float(
        related="company_id.sso_employee_rate", readonly=False
    )
    sso_employer_risk_rate = fields.Float(
        related="company_id.sso_employer_risk_rate", readonly=False
    )
    faov_employee_rate = fields.Float(
        related="company_id.faov_employee_rate", readonly=False
    )
    faov_employer_rate = fields.Float(
        related="company_id.faov_employer_rate", readonly=False
    )
    rpe_employee_rate = fields.Float(
        related="company_id.rpe_employee_rate", readonly=False
    )
    rpe_employer_rate = fields.Float(
        related="company_id.rpe_employer_rate", readonly=False
    )
    inces_employer_rate = fields.Float(
        related="company_id.inces_employer_rate", readonly=False
    )
    inces_min_employees = fields.Integer(
        related="company_id.inces_min_employees", readonly=False
    )
    cepp_employer_rate = fields.Float(
        related="company_id.cepp_employer_rate", readonly=False
    )
    profit_sharing_days = fields.Integer(
        related="company_id.profit_sharing_days", readonly=False
    )
    meal_ticket_amount = fields.Monetary(
        related="company_id.meal_ticket_amount",
        readonly=False,
        currency_field="currency_id",
    )
    faov_account_number = fields.Char(
        related="company_id.faov_account_number", readonly=False
    )
    ivss_employer_number = fields.Char(
        related="company_id.ivss_employer_number", readonly=False
    )
    partner_ivss_id = fields.Many2one(
        related="company_id.partner_ivss_id", readonly=False
    )
    partner_banavih_id = fields.Many2one(
        related="company_id.partner_banavih_id", readonly=False
    )
