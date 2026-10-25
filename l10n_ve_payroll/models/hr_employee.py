# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_ve_worker_type = fields.Selection(
        [
            ("employee", "Employee"),
            ("contractor", "Contractor"),
            ("intern", "Intern"),
        ],
        string="Worker Type",
        default="employee",
    )
    l10n_ve_workday_type = fields.Selection(
        [
            ("diurnal", "Diurnal"),
            ("nocturnal", "Nocturnal"),
            ("mixed", "Mixed"),
        ],
        string="Workday Type",
        default="diurnal",
    )
    l10n_ve_is_unionized = fields.Boolean(string="Unionized")
    l10n_ve_islr_rate = fields.Float(string="ISLR Rate (%)")
    l10n_ve_has_disability = fields.Boolean(string="Has Disability")
    social_benefit_ids = fields.One2many(
        "l10n_ve.payroll.social.benefit",
        "employee_id",
        string="Social Benefits",
    )
    l10n_ve_currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Company Currency",
    )
    l10n_ve_social_benefit_balance = fields.Monetary(
        string="Social Benefit Balance",
        currency_field="l10n_ve_currency_id",
        compute="_compute_l10n_ve_social_benefit_totals",
    )
    l10n_ve_social_benefit_interest_balance = fields.Monetary(
        string="Social Benefit Interest Balance",
        currency_field="l10n_ve_currency_id",
        compute="_compute_l10n_ve_social_benefit_totals",
    )

    def _compute_l10n_ve_social_benefit_totals(self):
        for employee in self:
            benefits = employee.social_benefit_ids
            employee.l10n_ve_social_benefit_balance = sum(benefits.mapped("balance"))
            employee.l10n_ve_social_benefit_interest_balance = sum(
                benefits.mapped("interest_ids").mapped("amount")
            )
