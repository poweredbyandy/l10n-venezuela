from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_fiscal_serial_flag_21 = fields.Selection(
        related="company_id.l10n_ve_fiscal_serial_flag_21",
        readonly=False,
    )

    l10n_ve_fiscal_serial_use_emulator = fields.Boolean(
        related="company_id.l10n_ve_fiscal_serial_use_emulator",
        readonly=False,
    )
    l10n_ve_fiscal_serial_send_default_code_in_name = fields.Boolean(
        related="company_id.l10n_ve_fiscal_serial_send_default_code_in_name",
        readonly=False,
    )
