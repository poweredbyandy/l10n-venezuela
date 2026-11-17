from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_own_fleet = fields.Boolean(
        related="company_id.l10n_ve_own_fleet",
        readonly=False,
    )
