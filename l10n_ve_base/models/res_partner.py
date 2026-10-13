from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    taxpayer_type = fields.Selection(
        [
            ("ordinary", "Ordinary"),
            ("formal", "Formal"),
            ("special", "Special"),
        ],
    )
