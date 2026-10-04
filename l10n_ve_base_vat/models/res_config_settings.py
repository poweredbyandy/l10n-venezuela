# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_validate_partner_vat_format = fields.Boolean(
        related="company_id.l10n_ve_validate_partner_vat_format",
        readonly=False,
    )
