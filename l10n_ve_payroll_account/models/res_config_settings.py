# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    loan_receivable_account_id = fields.Many2one(
        related="company_id.loan_receivable_account_id",
        readonly=False,
        check_company=True,
    )
