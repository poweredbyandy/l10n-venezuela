from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    account_customer_advance_id = fields.Many2one(
        related="company_id.account_customer_advance_id",
        readonly=False,
    )
    account_supplier_advance_id = fields.Many2one(
        related="company_id.account_supplier_advance_id",
        readonly=False,
    )
