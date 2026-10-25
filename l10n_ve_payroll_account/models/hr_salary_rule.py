# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    l10n_ve_account_code_debit = fields.Char(
        string="SENIAT Debit Account Code",
        help="Optional chart code hint for post-init mapping (e.g. 2103020).",
    )
    l10n_ve_account_code_credit = fields.Char(
        string="SENIAT Credit Account Code",
    )
