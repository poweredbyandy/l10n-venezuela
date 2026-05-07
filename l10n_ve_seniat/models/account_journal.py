from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_emission_medium = fields.Selection(
        selection=[
            (
                "free",
                _("Forma libre (correlativo de talonario)"),
            ),
            (
                "contingency",
                _("Contingencia"),
            ),
            (
                "fiscal_machine",
                _("Máquina fiscal"),
            ),
            (
                "digital",
                _("Facturación digital"),
            ),
        ],
        string=_("Medio de emisión"),
        default="free",
        copy=False,
        help=_(
            "Forma libre: asigna correlativo desde el talonario interno. "
            "Contingencia: no usa el talonario; el N° de control se indica en la "
            "factura antes de confirmar. Máquina fiscal y facturación digital: "
            "tampoco generan correlativo automático del talonario; el N° de control "
            "debe consignarse manualmente antes de confirmar."
        ),
    )

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

    l10n_ve_fiscal_payment_code = fields.Char(
        string=_("Código forma de pago fiscal"),
        size=2,
        copy=False,
        help=_(
            "Código numérico de forma de pago para máquina fiscal TFHKA (01–24). "
            "Se usa al enviar pagos en la impresión fiscal cuando el registro proviene "
            "de este diario."
        ),
    )

    @api.constrains("l10n_ve_fiscal_payment_code")
    def _check_l10n_ve_fiscal_payment_code(self):
        for journal in self:
            raw = (journal.l10n_ve_fiscal_payment_code or "").strip()
            if not raw:
                continue
            if len(raw) != 2 or not raw.isdigit():
                raise ValidationError(
                    _(
                        "El código forma de pago fiscal del diario “%(journal)s” debe ser "
                        "dos dígitos (ej.: 01)."
                    )
                    % {"journal": journal.display_name}
                )
            value = int(raw)
            if value < 1 or value > 24:
                raise ValidationError(
                    _(
                        "El código forma de pago fiscal del diario “%(journal)s” debe estar "
                        "entre 01 y 24."
                    )
                    % {"journal": journal.display_name}
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
