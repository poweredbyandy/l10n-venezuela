from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    tfhka_iva_supplier_retention_edi_serie = fields.Char(
        related="company_id.iva_supplier_retention_journal_id.l10n_ve_edi_tfhka_serie",
        readonly=False,
    )
    tfhka_iva_supplier_retention_edi_sucursal = fields.Char(
        related="company_id.iva_supplier_retention_journal_id.l10n_ve_edi_tfhka_sucursal",
        readonly=False,
    )
    tfhka_islr_supplier_retention_edi_serie = fields.Char(
        related="company_id.islr_supplier_retention_journal_id.l10n_ve_edi_tfhka_serie",
        readonly=False,
    )
    tfhka_islr_supplier_retention_edi_sucursal = fields.Char(
        related="company_id.islr_supplier_retention_journal_id.l10n_ve_edi_tfhka_sucursal",
        readonly=False,
    )
