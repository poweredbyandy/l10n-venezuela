# Copyright 2026 Anderson Armeya
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    currency_index_id = fields.Many2one(
        related="company_id.currency_index_id",
        readonly=False,
    )
