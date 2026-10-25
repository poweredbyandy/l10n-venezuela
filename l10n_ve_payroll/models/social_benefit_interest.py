# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class L10nVePayrollSocialBenefitInterest(models.Model):
    _name = "l10n_ve.payroll.social.benefit.interest"
    _description = "Social Benefit Interest"
    _order = "date desc, id desc"

    benefit_id = fields.Many2one(
        "l10n_ve.payroll.social.benefit",
        required=True,
        ondelete="cascade",
    )
    date = fields.Date(required=True, default=fields.Date.context_today)
    rate = fields.Float(string="Rate (%)")
    amount = fields.Monetary(currency_field="currency_id")
    currency_id = fields.Many2one(related="benefit_id.currency_id", store=True)
    source_payslip_id = fields.Many2one("hr.payslip")
