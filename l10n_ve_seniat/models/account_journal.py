from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_invoice_section_id = fields.Many2one(
        "account.book.section",
        string="SENIAT fiscal book section (invoices)",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Tramo del talonario para facturas de cliente. Si la ND usa otro tramo, "
        "configúrelo en “Notas de débito”.",
    )
    l10n_ve_debit_note_section_id = fields.Many2one(
        "account.book.section",
        string="SENIAT fiscal book section (debit notes)",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Tramo opcional para notas de débito de cliente. Si está vacío, se usa "
        "el tramo de facturas.",
    )
    l10n_ve_credit_note_section_id = fields.Many2one(
        "account.book.section",
        string="SENIAT fiscal book section (credit notes)",
        copy=False,
        check_company=True,
        domain="[('company_id', '=', company_id)]",
        help="Tramo del talonario para notas de crédito de cliente (out_refund).",
    )

    @api.constrains(
        "l10n_ve_invoice_section_id",
        "l10n_ve_debit_note_section_id",
        "l10n_ve_credit_note_section_id",
        "company_id",
    )
    def _check_l10n_ve_sections_company(self):
        for journal in self:
            for sec in (
                journal.l10n_ve_invoice_section_id,
                journal.l10n_ve_debit_note_section_id,
                journal.l10n_ve_credit_note_section_id,
            ):
                if sec and sec.company_id != journal.company_id:
                    raise ValidationError(
                        _(
                            "The fiscal book section “%(sec)s” belongs to another "
                            "company than journal “%(journal)s”."
                        )
                        % {
                            "sec": sec.display_name,
                            "journal": journal.display_name,
                        }
                    )
