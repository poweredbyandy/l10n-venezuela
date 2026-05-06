from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    l10n_ve_invoice_journal_display_name = fields.Char(
        string="Invoice journal display name (VE POS)",
        related="invoice_journal_id.display_name",
        readonly=True,
    )
    l10n_ve_invoice_journal_emission_medium = fields.Selection(
        related="invoice_journal_id.l10n_ve_emission_medium",
        readonly=True,
    )
    l10n_ve_pos_free_book_section_name = fields.Char(
        compute="_compute_l10n_ve_pos_invoice_journal_ve_hints",
        string="VE talonario (forma libre)",
    )
    l10n_ve_pos_next_free_control_number = fields.Char(
        compute="_compute_l10n_ve_pos_invoice_journal_ve_hints",
        string="Próximo N° control (forma libre)",
    )

    @api.depends(
        "invoice_journal_id",
        "invoice_journal_id.l10n_ve_emission_medium",
        "invoice_journal_id.l10n_ve_invoice_section_id",
        "company_id.account_fiscal_country_id",
    )
    def _compute_l10n_ve_pos_invoice_journal_ve_hints(self):
        for config in self:
            config.l10n_ve_pos_free_book_section_name = False
            config.l10n_ve_pos_next_free_control_number = False
            if config.company_id.account_fiscal_country_id.code != "VE":
                continue
            journal = config.invoice_journal_id
            if not journal or journal.l10n_ve_emission_medium != "free":
                continue
            section = journal.l10n_ve_invoice_section_id
            if not section:
                continue
            book = section.book_id
            config.l10n_ve_pos_free_book_section_name = section.display_name
            if book:
                config.l10n_ve_pos_next_free_control_number = (
                    book.l10n_ve_peek_next_formatted(section) or ""
                )
