# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_validate_partner_vat_format = fields.Boolean(
        string="Validar formato de RIF/CI",
        default=True,
    )
