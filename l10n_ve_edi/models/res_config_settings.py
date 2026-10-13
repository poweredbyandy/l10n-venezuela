from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_has_digital_billing_emission = fields.Boolean(
        compute="_compute_l10n_ve_has_digital_billing_emission",
    )

    @api.depends("company_id")
    def _compute_l10n_ve_has_digital_billing_emission(self):
        for settings in self:
            settings.l10n_ve_has_digital_billing_emission = bool(
                settings.company_id
                and settings.company_id._l10n_ve_has_emission_medium("digital_billing")
            )

    l10n_ve_edi_iva_supplier_retention_provider = fields.Selection(
        related="company_id.iva_supplier_retention_journal_id.l10n_ve_edi_provider",
        string="IVA digital billing provider",
        readonly=False,
    )
    l10n_ve_edi_islr_supplier_retention_provider = fields.Selection(
        related="company_id.islr_supplier_retention_journal_id.l10n_ve_edi_provider",
        string="ISLR digital billing provider",
        readonly=False,
    )
