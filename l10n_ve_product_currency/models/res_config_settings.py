from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_product_currency_default_force_currency_id = fields.Many2one(
        "res.currency",
        string="Default Product Currency",
        config_parameter="l10n_ve_product_currency.default_force_currency_id",
        help="If empty, new products use the company currency.",
    )
