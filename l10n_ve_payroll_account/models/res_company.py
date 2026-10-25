# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    loan_receivable_account_id = fields.Many2one(
        "account.account",
        string="Loan Receivable Account",
        check_company=True,
        domain="[('account_type', '=', 'asset_receivable'), ('deprecated', '=', False)]",
        help="Default debit account for employee loan disbursements (SENIAT 1106002).",
    )
