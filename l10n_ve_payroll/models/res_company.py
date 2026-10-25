# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    minimum_wage = fields.Monetary(
        string="Minimum Wage",
        currency_field="currency_id",
        help="Legal minimum wage in company currency (VES).",
    )
    sso_employee_rate = fields.Float(string="SSO Employee Rate (%)", default=4.0)
    sso_employer_risk_rate = fields.Float(
        string="SSO Employer Risk Rate (%)", default=10.0
    )
    faov_employee_rate = fields.Float(string="FAOV Employee Rate (%)", default=1.0)
    faov_employer_rate = fields.Float(string="FAOV Employer Rate (%)", default=2.0)
    rpe_employee_rate = fields.Float(string="RPE Employee Rate (%)", default=0.5)
    rpe_employer_rate = fields.Float(string="RPE Employer Rate (%)", default=2.0)
    inces_employer_rate = fields.Float(string="INCES Employer Rate (%)", default=2.0)
    inces_min_employees = fields.Integer(
        string="INCES Minimum Employees",
        default=5,
        help="Apply INCES when the company has at least this many employees.",
    )
    cepp_employer_rate = fields.Float(
        string="CEPP Employer Rate (%)",
        default=9.0,
        help="Special pension contribution (CEPP).",
    )
    profit_sharing_days = fields.Integer(string="Profit Sharing Days", default=30)
    meal_ticket_amount = fields.Monetary(
        string="Meal Ticket Amount",
        currency_field="currency_id",
    )
    faov_account_number = fields.Char(string="FAOV Account Number")
    ivss_employer_number = fields.Char(string="IVSS Employer Number")
    partner_ivss_id = fields.Many2one("res.partner", string="IVSS Partner")
    partner_banavih_id = fields.Many2one("res.partner", string="BANAVIH Partner")
