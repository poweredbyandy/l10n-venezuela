# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class L10nVePayrollSocialBenefit(models.Model):
    _name = "l10n_ve.payroll.social.benefit"
    _description = "Venezuelan Social Benefit Accrual"
    _order = "date desc, id desc"

    name = fields.Char(required=True)
    employee_id = fields.Many2one("hr.employee", required=True, index=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id", store=True, readonly=True
    )
    date = fields.Date(required=True, default=fields.Date.context_today)
    amount = fields.Monetary(currency_field="currency_id")
    balance = fields.Monetary(currency_field="currency_id")
    benefit_type = fields.Selection(
        [
            ("accrual", "Accrual"),
            ("interest", "Interest"),
            ("payment", "Payment"),
            ("settlement", "Settlement"),
        ],
        required=True,
        default="accrual",
    )
    source_payslip_id = fields.Many2one("hr.payslip", string="Source Payslip")
    interest_ids = fields.One2many(
        "l10n_ve.payroll.social.benefit.interest",
        "benefit_id",
        string="Interests",
    )
    notes = fields.Text()
