from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_edi_iva_supplier_retention_provider = fields.Selection(
        related="company_id.iva_supplier_retention_journal_id.l10n_ve_edi_provider",
        readonly=False,
    )
    l10n_ve_edi_islr_supplier_retention_provider = fields.Selection(
        related="company_id.islr_supplier_retention_journal_id.l10n_ve_edi_provider",
        readonly=False,
    )
