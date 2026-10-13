from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    taxpayer_type = fields.Selection(
        related="partner_id.taxpayer_type",
        readonly=False,
    )
