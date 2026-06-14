from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_igtf_enabled = fields.Boolean(
        related="company_id.l10n_ve_igtf_enabled",
        readonly=False,
    )
    l10n_ve_igtf_settings_eligible = fields.Boolean(
        compute="_compute_l10n_ve_igtf_settings_eligible",
        string="Show IGTF settings (Venezuela, special taxpayer)",
    )

    l10n_ve_igtf_account_id = fields.Many2one(
        related="company_id.l10n_ve_igtf_account_id",
        readonly=False,
        domain="[('account_type', 'in', ('liability_current', 'liability_non_current'))]",
    )
    l10n_ve_igtf_percent = fields.Float(
        related="company_id.l10n_ve_igtf_percent",
        readonly=False,
    )

    l10n_ve_igtf_currency_ids = fields.Many2many(
        related="company_id.l10n_ve_igtf_currency_ids",
        readonly=False,
    )
    l10n_ve_igtf_allow_invoice_accrual = fields.Boolean(
        related="company_id.l10n_ve_igtf_allow_invoice_accrual",
        readonly=False,
    )

    l10n_ve_is_ve_country = fields.Boolean(
        compute="_compute_l10n_ve_is_ve_country",
        store=False,
    )

    @api.depends(
        "company_id.account_fiscal_country_id",
        "company_id.taxpayer_type",
    )
    def _compute_l10n_ve_igtf_settings_eligible(self):
        for record in self:
            c = record.company_id
            record.l10n_ve_igtf_settings_eligible = (
                bool(c.account_fiscal_country_id)
                and c.account_fiscal_country_id.code == "VE"
                and c.taxpayer_type == "special"
            )

    @api.depends("company_id.account_fiscal_country_id")
    def _compute_l10n_ve_is_ve_country(self):
        for record in self:
            record.l10n_ve_is_ve_country = (
                record.company_id.account_fiscal_country_id
                and record.company_id.account_fiscal_country_id.code == "VE"
            )
