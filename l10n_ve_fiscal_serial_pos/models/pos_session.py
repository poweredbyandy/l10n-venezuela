from odoo import api, fields, models


class PosSession(models.Model):
    _inherit = "pos.session"

    l10n_ve_journal_emission_medium = fields.Selection(
        related="config_id.l10n_ve_invoice_journal_emission_medium",
    )
    l10n_ve_show_fiscal_report_z_button = fields.Boolean(
        compute="_compute_l10n_ve_show_fiscal_report_z_button",
    )

    @api.depends(
        "company_id.account_fiscal_country_id",
        "config_id.l10n_ve_invoice_journal_emission_medium",
        "state",
    )
    def _compute_l10n_ve_show_fiscal_report_z_button(self):
        for session in self:
            session.l10n_ve_show_fiscal_report_z_button = (
                session.company_id.account_fiscal_country_id.code == "VE"
                and session.config_id.l10n_ve_invoice_journal_emission_medium
                == "fiscal_machine"
                and session.state in ("closing_control", "closed")
            )
