from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    l10n_ve_pos_igtf_percent = fields.Float(
        related="company_id.l10n_ve_igtf_percent",
        readonly=False,
        string="IGTF (%)",
    )
