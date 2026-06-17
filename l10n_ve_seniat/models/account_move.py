import logging
import re

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.float_utils import float_compare
from odoo.tools.mail import html2plaintext
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)

_L10N_VE_CANCEL_REASON_MOVE_TYPES = (
    "out_invoice",
    "out_refund",
    "out_receipt",
)


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_process_date = fields.Date(
        string="Fecha de proceso",
        copy=False,
        tracking=True,
    )
    seniat_invoice_tag = fields.Html(
        string="SENIAT Invoice Tag",
        readonly=True,
        compute="_compute_seniat_invoice_tag",
    )
    l10n_ve_origin_affected_total_company = fields.Monetary(
        string="Total documento origen (moneda compañía)",
        currency_field="company_currency_id",
        compute="_compute_l10n_ve_origin_affected_total_company",
    )

    @api.depends(
        "debit_origin_id",
        "reversed_entry_id",
        "debit_origin_id.tax_totals",
        "reversed_entry_id.tax_totals",
        "debit_origin_id.amount_total",
        "debit_origin_id.currency_id",
        "reversed_entry_id.amount_total",
        "reversed_entry_id.currency_id",
        "company_currency_id",
    )
    def _compute_l10n_ve_origin_affected_total_company(self):
        for move in self:
            origin = move.debit_origin_id or move.reversed_entry_id
            if not origin:
                move.l10n_ve_origin_affected_total_company = False
                continue
            tt = origin.tax_totals or {}
            if isinstance(tt, dict) and "total_amount" in tt:
                move.l10n_ve_origin_affected_total_company = tt["total_amount"]
            elif origin.currency_id == origin.company_currency_id:
                move.l10n_ve_origin_affected_total_company = origin.amount_total
            else:
                move.l10n_ve_origin_affected_total_company = False

    @api.depends(
        "company_id",
        "company_id.taxpayer_type",
        "l10n_ve_inverse_rate",
        "move_type",
        "country_code",
        "debit_origin_id",
        "reversed_entry_id",
    )
    def _compute_seniat_invoice_tag(self):
        for move in self:
            if move.country_code == "VE" and move.move_type in (
                "out_invoice",
                "out_refund",
            ):
                texts = []
                if move.company_id._l10n_ve_invoice_tag_include_igtf_notice():
                    texts.append(
                        "<span>Este pago estará sujeto al cobro adicional del 3% del "
                        "Impuesto a las Grandes Transacciones Financieras (IGTF), de "
                        "conformidad con la Providencia Administrativa SNAT/2022/000013 "
                        "publicada en la G.O N 42.339 del 17-03-2022, en caso de ser "
                        "cancelado en divisas. No aplica en pago en Bs.</span> "
                    )
                # Segundo texto sobre tipo de cambio (solo si hay tasa inversa)
                if move.company_currency_id != move.currency_id:
                    # Formatear la tasa inversa con la moneda de la compañía
                    rate_formatted = move.company_currency_id.format(
                        move.l10n_ve_inverse_rate
                    )
                    texts.append(
                        "<span>Este documento se expresa en Bolívares con su "
                        "equivalente en Divisas, al tipo de cambio corriente del "
                        "mercado a la fecha de su emisión, según lo establecido en "
                        "el articulo 13 numeral 14 de la providencia administrativa "
                        "SNAT/2011/0071 "
                        f"({rate_formatted}) en concordancia con el articulo 128 "
                        "de la Ley del Banco Central de Venezuela (BCV); articulo 15 "
                        "de la Ley que establece el impuesto al valor agregado (IVA) "
                        "y 38 del Reglamento General de la Ley que establece el "
                        "Impuesto de Valor agregado (RLIVA)</span>"
                    )
                if not texts and (
                    move.move_type == "out_refund" or move.debit_origin_id
                ):
                    texts.append(
                        "<span>%s</span>"
                        % _(
                            "Este documento se expresa conforme a la normativa "
                            "tributaria vigente (SENIAT)."
                        )
                    )
                move.seniat_invoice_tag = "".join(texts) if texts else False
            else:
                move.seniat_invoice_tag = False

    def write(self, vals):
        if not self.env.context.get("l10n_ve_skip_credit_debit_journal_lock") and (
            "journal_id" in vals or "partner_id" in vals
        ):
            for move in self:
                if move.l10n_ve_lock_credit_debit_journal:
                    raise UserError(
                        _(
                            "No puede modificar el diario ni el contacto en notas de "
                            "crédito o débito para empresas con fiscalidad venezolana."
                        )
                    )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._l10n_ve_sync_journal_with_origin_from_create()
        return records

    l10n_ve_invoice_original_printed = fields.Boolean(
        string="VE Invoice Original Printed",
        copy=False,
        readonly=True,
        help=(
            "Technical flag used by the VE invoice report to determine if a printed "
            "copy should display a 'faithful copy' label."
        ),
    )
    l10n_ve_hide_invoice_preview_send = fields.Boolean(
        compute="_compute_l10n_ve_hide_invoice_preview_send",
    )
    l10n_ve_hide_invoice_print_pdf = fields.Boolean(
        compute="_compute_l10n_ve_hide_invoice_print_pdf",
    )
    l10n_ve_digital_invoice_sent = fields.Boolean(
        compute="_compute_l10n_ve_digital_invoice_sent",
    )

    @api.depends(
        "country_code",
        "move_type",
        "state",
        "l10n_ve_invoice_original_printed",
        "l10n_ve_journal_emission_medium",
    )
    def _compute_l10n_ve_hide_invoice_preview_send(self):
        for move in self:
            move.l10n_ve_hide_invoice_preview_send = False
            if move.country_code != "VE":
                continue
            if move.move_type not in ("out_invoice", "out_refund"):
                continue
            if move.state != "posted":
                continue
            if move._l10n_ve_blocking_invoice_report_before_digital_sent():
                move.l10n_ve_hide_invoice_preview_send = True
                continue
            medium = move.l10n_ve_journal_emission_medium
            if medium == "contingency":
                move.l10n_ve_hide_invoice_preview_send = True
                continue
            if medium == "digital":
                continue
            if not move.l10n_ve_invoice_original_printed:
                move.l10n_ve_hide_invoice_preview_send = True

    @api.depends(
        "country_code",
        "move_type",
        "state",
        "l10n_ve_journal_emission_medium",
    )
    def _compute_l10n_ve_hide_invoice_print_pdf(self):
        for move in self:
            move.l10n_ve_hide_invoice_print_pdf = False
            if move.country_code != "VE":
                continue
            if move.move_type not in ("out_invoice", "out_refund"):
                continue
            if move.l10n_ve_journal_emission_medium == "contingency":
                move.l10n_ve_hide_invoice_print_pdf = True
                continue
            if move.state != "posted":
                continue
            if move._l10n_ve_blocking_invoice_report_before_digital_sent():
                move.l10n_ve_hide_invoice_print_pdf = True

    @api.depends(
        "country_code",
        "move_type",
        "l10n_ve_journal_emission_medium",
    )
    def _compute_l10n_ve_digital_invoice_sent(self):
        for move in self:
            move.l10n_ve_digital_invoice_sent = False
            if move.country_code != "VE" or move.move_type not in (
                "out_invoice",
                "out_refund",
            ):
                continue
            if move.l10n_ve_journal_emission_medium != "digital":
                continue
            send = getattr(move, "l10n_ve_edi_send_state", None)
            move.l10n_ve_digital_invoice_sent = send == "sent"

    l10n_ve_show_credit_debit_actions = fields.Boolean(
        compute="_compute_l10n_ve_show_credit_debit_actions",
    )

    @api.depends(
        "country_code",
        "move_type",
        "state",
        "l10n_ve_journal_emission_medium",
        "l10n_ve_invoice_original_printed",
        "l10n_ve_digital_invoice_sent",
    )
    def _compute_l10n_ve_show_credit_debit_actions(self):
        for move in self:
            move.l10n_ve_show_credit_debit_actions = (
                move._l10n_ve_allows_credit_debit_actions()
            )

    def _l10n_ve_invoice_emitted_for_credit_debit(self):
        self.ensure_one()
        medium = self.l10n_ve_journal_emission_medium
        if not medium or medium == "contingency":
            return True
        if medium == "free":
            return bool(self.l10n_ve_invoice_original_printed)
        if medium == "digital":
            return bool(self.l10n_ve_digital_invoice_sent)
        if medium == "fiscal_machine":
            return bool(self.l10n_ve_invoice_original_printed)
        return True

    def _l10n_ve_allows_credit_debit_actions(self):
        self.ensure_one()
        if self.move_type != "out_invoice":
            return False
        if self.country_code != "VE":
            return True
        if self.state != "posted":
            return False
        return self._l10n_ve_invoice_emitted_for_credit_debit()

    def _l10n_ve_check_credit_debit_allowed(self):
        for move in self:
            if move.country_code != "VE" or move.move_type != "out_invoice":
                continue
            if move._l10n_ve_allows_credit_debit_actions():
                continue
            medium = move.l10n_ve_journal_emission_medium
            if medium == "free":
                message = _(
                    "No puede crear una nota de crédito o débito: la factura debe "
                    "imprimirse en forma libre antes de revertirla."
                )
            elif medium == "digital":
                message = _(
                    "No puede crear una nota de crédito o débito: la factura debe "
                    "enviarse por facturación digital antes de revertirla."
                )
            elif medium == "fiscal_machine":
                message = _(
                    "No puede crear una nota de crédito o débito: la factura debe "
                    "imprimirse en máquina fiscal antes de revertirla."
                )
            else:
                message = _(
                    "No puede crear una nota de crédito o débito: la factura aún "
                    "no fue emitida."
                )
            raise UserError(message)

    def _l10n_ve_block_invoice_pdf_contingency(self):
        self.ensure_one()
        return (
            self.country_code == "VE"
            and self.move_type in ("out_invoice", "out_refund")
            and self.l10n_ve_journal_emission_medium == "contingency"
        )

    def _l10n_ve_blocking_invoice_report_before_digital_sent(self):
        self.ensure_one()
        if self.country_code != "VE":
            return False
        if self.move_type not in ("out_invoice", "out_refund"):
            return False
        if self.state != "posted":
            return False
        if self.l10n_ve_journal_emission_medium != "digital":
            return False
        if "l10n_ve_edi_send_state" not in self._fields:
            return True
        return self.l10n_ve_edi_send_state != "sent"

    reception_date = fields.Date(
        help="Indicates when the invoice was received by the client/company",
        tracking=True,
    )
    l10n_ve_invoice_date = fields.Datetime(
        string="Fecha del documento",
        copy=False,
        tracking=True,
        help=(
            "Forma libre: se asigna al confirmar. Contingencia: indíquela antes de "
            "confirmar. Facturación digital: fecha de sincronización con la imprenta. "
            "Máquina fiscal: fecha en que se imprimió el documento."
        ),
    )
    l10n_ve_control_number = fields.Char(
        string="Control Number",
        copy=False,
        store=True,
        tracking=True,
    )
    l10n_ve_control_number_placeholder = fields.Char(
        string="Próximo N° de control (previsto)",
        compute="_compute_l10n_ve_control_number_placeholder",
        readonly=True,
    )
    l10n_ve_show_control_number_ui = fields.Boolean(
        compute="_compute_l10n_ve_show_control_number_ui",
    )
    l10n_ve_journal_emission_medium = fields.Selection(
        related="journal_id.l10n_ve_emission_medium",
        string="Medio de emisión (diario)",
        readonly=True,
    )
    l10n_ve_serial_number = fields.Char(
        string="Fiscal Machine Serial",
        copy=False,
        tracking=True,
        help="Serial number of the fiscal machine",
    )
    l10n_ve_invoice_number = fields.Char(
        string="Fiscal Invoice Number",
        copy=False,
        tracking=True,
        help="Invoice number from the fiscal machine",
    )
    l10n_ve_report_z = fields.Char(
        string="Report Z Number",
        copy=False,
        tracking=True,
        help="Report Z number from the fiscal machine",
    )
    l10n_ve_on_behalf_of_third_party_enabled = fields.Boolean(
        related="company_id.l10n_ve_on_behalf_of_third_party_enabled",
        readonly=True,
    )
    l10n_ve_on_behalf_of_third_party = fields.Boolean(
        string="Indicador por cuenta de terceros",
        compute="_compute_l10n_ve_on_behalf_of_third_party",
        store=True,
        copy=False,
        help=(
            "Verdadero si hay un contacto en Por cuenta de Terceros en "
            "facturas de cliente. Según Art. 11 PA00071, esas operaciones "
            "deben emitirse en forma libre."
        ),
    )
    l10n_ve_third_party_partner_id = fields.Many2one(
        "res.partner",
        string="Por cuenta de Terceros",
        copy=False,
        ondelete="restrict",
    )
    l10n_ve_cancel_reason_id = fields.Many2one(
        "l10n_ve.invoice.cancel.reason",
        string="Motivo de anulación",
        copy=False,
        readonly=True,
        tracking=True,
    )

    @api.depends("l10n_ve_third_party_partner_id", "move_type")
    def _compute_l10n_ve_on_behalf_of_third_party(self):
        for move in self:
            move.l10n_ve_on_behalf_of_third_party = bool(
                move.l10n_ve_third_party_partner_id
                and move.move_type in ("out_invoice", "out_refund")
            )

    l10n_ve_certified_copy_deadline = fields.Date(
        string="Plazo entrega copia certificada",
        compute="_compute_l10n_ve_certified_copy_deadline",
        store=True,
        help="Día 5 del mes siguiente a la emisión (Art. 32 PA00071).",
    )
    l10n_ve_certified_copy_delivered = fields.Boolean(
        string="Copia certificada entregada",
        copy=False,
    )
    l10n_ve_certified_copy = fields.Binary(
        string="Copia certificada adjunta",
        attachment=True,
        copy=False,
    )
    l10n_ve_certified_copy_filename = fields.Char(
        string="Nombre archivo copia certificada",
        copy=False,
    )

    @api.depends("invoice_date", "l10n_ve_on_behalf_of_third_party")
    def _compute_l10n_ve_certified_copy_deadline(self):
        for move in self:
            if move.l10n_ve_on_behalf_of_third_party and move.invoice_date:
                next_month = move.invoice_date + relativedelta(months=1)
                move.l10n_ve_certified_copy_deadline = next_month.replace(day=5)
            else:
                move.l10n_ve_certified_copy_deadline = False

    def _l10n_ve_to_company_abs_amount(self):
        self.ensure_one()
        company_cur = self.company_currency_id
        amount = abs(self.amount_total)
        if self.currency_id == company_cur:
            return company_cur.round(amount)
        date = self.invoice_date or self.date or fields.Date.context_today(self)
        return company_cur.round(
            self.currency_id._convert(amount, company_cur, self.company_id, date)
        )

    def _l10n_ve_credit_note_limit_company_amount(self):
        self.ensure_one()
        if self.move_type != "out_refund" or not self.reversed_entry_id:
            return 0.0
        company_cur = self.company_currency_id
        origin = self.reversed_entry_id
        limit = origin._l10n_ve_to_company_abs_amount()
        debit_notes = origin.debit_note_ids.filtered(
            lambda m: m.state == "posted" and m.move_type == "out_invoice"
        )
        for debit in debit_notes:
            limit = company_cur.round(limit + debit._l10n_ve_to_company_abs_amount())
        return limit

    def _l10n_ve_credit_note_accumulated_company_amount(self, include_current=False):
        self.ensure_one()
        if self.move_type != "out_refund" or not self.reversed_entry_id:
            return 0.0
        company_cur = self.company_currency_id
        origin = self.reversed_entry_id
        total = 0.0
        posted_credits = origin.reversal_move_ids.filtered(
            lambda m: m.state == "posted" and m.move_type == "out_refund"
        )
        for credit in posted_credits:
            total = company_cur.round(total + credit._l10n_ve_to_company_abs_amount())
        if include_current and self.state != "posted":
            total = company_cur.round(total + self._l10n_ve_to_company_abs_amount())
        return total

    def _l10n_ve_validate_credit_note_amount_limit(self):
        self.ensure_one()
        ve_code = self.env.ref("base.ve").code
        if self.country_code != ve_code or self.move_type != "out_refund":
            return
        if not self.reversed_entry_id:
            return
        company_cur = self.company_currency_id
        limit = self._l10n_ve_credit_note_limit_company_amount()
        accumulated = self._l10n_ve_credit_note_accumulated_company_amount(
            include_current=True
        )
        if float_compare(accumulated, limit, precision_rounding=company_cur.rounding) > 0:
            origin = self.reversed_entry_id
            raise ValidationError(
                _(
                    "No se puede confirmar la nota de crédito '%(move)s'. "
                    "El monto acumulado de notas de crédito (%(accumulated)s) "
                    "supera el monto máximo permitido (%(limit)s) del documento "
                    "origen '%(origin)s'."
                )
                % {
                    "move": self.name or _("Borrador"),
                    "accumulated": formatLang(
                        self.env,
                        accumulated,
                        currency_obj=company_cur,
                    ),
                    "limit": formatLang(
                        self.env,
                        limit,
                        currency_obj=company_cur,
                    ),
                    "origin": origin.display_name,
                }
            )

    def _l10n_ve_validate_customer_invoice_emission_for_post(self):
        self.ensure_one()
        if self.country_code != self.env.ref("base.ve").code:
            return
        if self.move_type not in ("out_invoice", "out_refund"):
            return
        journal = self.journal_id
        if not journal or journal.type != "sale":
            return
        medium = journal.l10n_ve_emission_medium
        if not medium:
            return
        if medium == "contingency":
            if not self.l10n_ve_invoice_date:
                raise ValidationError(
                    _(
                        "No se puede confirmar el documento “%(doc)s”. "
                        "En contingencia debe indicar la fecha del documento."
                    )
                    % {"doc": self.name or _("Borrador")}
                )
        if medium == "free":
            if (self.l10n_ve_control_number or "").strip():
                return
            if not self._l10n_ve_journal_fiscal_book_section():
                raise ValidationError(
                    _(
                        "No se puede confirmar el documento “%(doc)s”. "
                        "Configure los tramos del talonario (SENIAT) en el "
                        "diario de ventas “%(journal)s”."
                    )
                    % {
                        "doc": self.name or _("Borrador"),
                        "journal": journal.display_name,
                    }
                )
        elif medium == "fiscal_machine":
            if self.l10n_ve_on_behalf_of_third_party:
                if not (self.l10n_ve_control_number or "").strip():
                    raise ValidationError(
                        _(
                            "No se puede confirmar el documento “%(doc)s”. "
                            "Indique el N° de control SENIAT (este diario no usa "
                            "correlativo automático del talonario)."
                        )
                        % {"doc": self.name or _("Borrador")}
                    )
        elif medium == "digital":
            return
        elif medium != "fiscal_machine" and not (
            self.l10n_ve_control_number or ""
        ).strip():
            if medium == "contingency":
                raise ValidationError(
                    _(
                        "No se puede confirmar el documento “%(doc)s”. "
                        "En contingencia el N° de control SENIAT es obligatorio."
                    )
                    % {"doc": self.name or _("Borrador")}
                )
            raise ValidationError(
                _(
                    "No se puede confirmar el documento “%(doc)s”. "
                    "Indique el N° de control SENIAT (este diario no usa "
                    "correlativo automático del talonario)."
                )
                % {"doc": self.name or _("Borrador")}
            )

    def _l10n_ve_validate_partner_vat_format_enabled(self):
        self.ensure_one()
        return self.company_id.l10n_ve_validate_partner_vat_format

    def _l10n_ve_partner_requires_rif_validation(self, partner):
        self.ensure_one()
        country = partner.country_id or partner.commercial_partner_id.country_id
        return bool(country and country.code == "VE")

    def action_post(self):  # noqa: C901
        if self.env.context.get("install_mode"):
            return super().action_post()
        for move_id in self:
            if move_id.country_code != self.env.ref("base.ve").code:
                continue

            move_id._l10n_ve_validate_customer_invoice_emission_for_post()

            if move_id.move_type in (
                "out_invoice",
                "out_refund",
                "in_invoice",
                "in_refund",
            ):
                partner = move_id.partner_id
                partner_requires_rif = move_id._l10n_ve_partner_requires_rif_validation(
                    partner
                )
                if partner_requires_rif and not partner.vat:
                    raise ValidationError(
                        _(
                            "No se puede confirmar la factura '%(move)s'. "
                            "El contacto '%(partner)s' no tiene el RIF (VAT) "
                            "configurado."
                        )
                        % {
                            "move": move_id.name or _("Borrador"),
                            "partner": partner.name,
                        }
                    )
                if (
                    partner_requires_rif
                    and move_id._l10n_ve_validate_partner_vat_format_enabled()
                    and not partner.check_vat_ve(partner.vat)
                ):
                    raise ValidationError(
                        _(
                            "No se puede confirmar la factura '%(move)s'. "
                            "El RIF '%(vat)s' del contacto '%(partner)s' no tiene un "
                            "formato válido. El formato correcto es: [V/E/J/C/P/G] "
                            "seguido del número de identificación (ej: V12345678, "
                            "J-12.345.678-9)."
                        )
                        % {
                            "move": move_id.name or _("Borrador"),
                            "vat": partner.vat,
                            "partner": partner.name,
                        }
                    )

                # Validar que el total de la factura no sea 0
                if abs(move_id.amount_total) < 0.01:
                    raise ValidationError(
                        _(
                            "No se puede facturar con un total de 0. Por favor, "
                            "verifique las líneas de la factura."
                        )
                    )

                if (
                    move_id.move_type in ("out_refund", "in_refund")
                    and not move_id.reversed_entry_id
                ):
                    raise ValidationError(
                        _(
                            "No se puede confirmar la nota de crédito '%(move)s'. "
                            "Debe indicar el documento origen (factura afectada)."
                        )
                        % {"move": move_id.name or _("Borrador")}
                    )

                if move_id.l10n_ve_third_party_partner_id and move_id.move_type in (
                    "out_invoice",
                    "out_refund",
                    "in_invoice",
                    "in_refund",
                ):
                    if not move_id.l10n_ve_on_behalf_of_third_party_enabled:
                        raise ValidationError(
                            _(
                                "No se puede confirmar la factura por cuenta de "
                                "terceros '%(move)s'. Debe habilitar la opción "
                                "'Facturación por cuenta de terceros' en "
                                "Configuración > Contabilidad."
                            )
                            % {"move": move_id.name or _("Borrador")}
                        )
                    third = move_id.l10n_ve_third_party_partner_id
                    third_requires_rif = move_id._l10n_ve_partner_requires_rif_validation(
                        third
                    )
                    if third_requires_rif and not third.vat:
                        raise ValidationError(
                            _(
                                "No se puede confirmar la factura por cuenta de "
                                "terceros '%(move)s'. El tercero '%(third)s' no tiene "
                                "el RIF configurado."
                            )
                            % {
                                "move": move_id.name or _("Borrador"),
                                "third": third.name,
                            }
                        )
                    if (
                        third_requires_rif
                        and move_id._l10n_ve_validate_partner_vat_format_enabled()
                        and not third.check_vat_ve(third.vat)
                    ):
                        raise ValidationError(
                            _(
                                "No se puede confirmar la factura por cuenta de "
                                "terceros '%(move)s'. El RIF '%(vat)s' del tercero "
                                "'%(third)s' no tiene un formato válido."
                            )
                            % {
                                "move": move_id.name or _("Borrador"),
                                "vat": third.vat,
                                "third": third.name,
                            }
                        )

            lines = []
            for line in self.line_ids:
                if len(line.tax_ids) > 1:
                    tax_mapped = ", ".join(line.tax_ids.mapped("name"))
                    lines.append(f" - {line.name}: {tax_mapped}")

            if lines:
                raise UserError(
                    _(
                        "You cannot assign more than one tax to a single invoice line. "
                        "Please create separate lines for each tax. \n"
                        "%s"
                    )
                    % ("\n".join(lines))
                )
        return super().action_post()

    def action_l10n_ve_open_cancel_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group("l10n_ve_seniat.group_l10n_ve_invoice_void"):
            raise AccessError(_("No tiene permiso para anular facturas de cliente."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Anular documento"),
            "res_model": "l10n_ve.account.move.cancel.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_move_id": self.id},
        }

    def button_cancel(self):
        ve_code = self.env.ref("base.ve").code
        for move in self:
            if (
                move.country_code == ve_code
                and move.move_type in _L10N_VE_CANCEL_REASON_MOVE_TYPES
                and not move.l10n_ve_cancel_reason_id
            ):
                raise ValidationError(
                    _(
                        "Para anular este documento debe indicar el motivo mediante el "
                        "asistente (botón «Cancelar» en el encabezado)."
                    )
                )
        self = self.with_context(force_draft=True)
        return super().button_cancel()

    def button_draft(self):
        if self.country_code != self.env.ref("base.ve").code:
            return super().button_draft()

        if self.env.context.get("force_draft"):
            return super().button_draft()

        _logger.info("Button draft called on move %s", self.move_type)
        if self.move_type == "entry":
            res = super().button_draft()
            self.write({"l10n_ve_process_date": False})
            return res
        if self.move_type in ("in_invoice", "in_refund", "in_receipt"):
            res = super().button_draft()
            self.write({"l10n_ve_process_date": False})
            return res

        raise ValidationError(
            _("""You cannot reset to draft an invoice in the Venezuelan localization.
Please create a credit note instead.
        """)
        )

    def _post(self, soft=True):
        self._l10n_ve_check_credit_debit_journal_matches_origin()
        self._l10n_ve_check_credit_note_products_and_labels()
        if not self.env.context.get("install_mode"):
            for move in self:
                move._l10n_ve_validate_customer_invoice_emission_for_post()
                move._l10n_ve_validate_credit_note_amount_limit()
        res = super()._post(soft=soft)
        if self.env.context.get("install_mode"):
            return res
        ve_code = self.env.ref("base.ve").code
        for rec in self:
            if rec.state != "posted":
                continue
            if (
                rec.country_code == ve_code
                and rec.move_type in ("out_invoice", "out_refund")
                and not rec.l10n_ve_invoice_date
            ):
                rec.write({"l10n_ve_invoice_date": fields.Datetime.now()})
            if (
                rec.country_code == ve_code
                and rec.move_type in ("out_invoice", "out_refund")
                and not rec.l10n_ve_control_number
            ):
                rec._generate_control_number()
        posted_without_process_date = self.filtered(
            lambda move: move.state == "posted" and not move.l10n_ve_process_date
        )
        if posted_without_process_date:
            payment_moves = posted_without_process_date.filtered("origin_payment_id")
            for move in payment_moves:
                payment_date = move.origin_payment_id.l10n_ve_process_date
                if payment_date:
                    move.l10n_ve_process_date = payment_date
            other_moves = posted_without_process_date - payment_moves
            if other_moves:
                other_moves.write(
                    {"l10n_ve_process_date": fields.Date.context_today(self)}
                )
        return res

    def _l10n_ve_journal_fiscal_book_section(self):
        self.ensure_one()
        journal = self.journal_id
        if not journal or journal.type != "sale":
            return self.env["account.book.section"]
        if self.move_type == "out_invoice":
            if self.debit_origin_id and journal.l10n_ve_debit_note_section_id:
                return journal.l10n_ve_debit_note_section_id
            return journal.l10n_ve_invoice_section_id
        if self.move_type == "out_refund":
            return journal.l10n_ve_credit_note_section_id
        return self.env["account.book.section"]

    def _l10n_ve_fiscal_book(self):
        self.ensure_one()
        doc = self.env["account.book.document"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
            ],
            limit=1,
        )
        if doc:
            return doc.book_id
        section = self._l10n_ve_journal_fiscal_book_section()
        return section.book_id if section else self.env["account.book"]

    def _l10n_ve_get_invoice_paperformat(self):
        self.ensure_one()
        if self.country_code != "VE" or self.move_type not in ("out_invoice", "out_refund"):
            return self.env["report.paperformat"]
        book = self._l10n_ve_fiscal_book()
        return book.paperformat_id if book else self.env["report.paperformat"]

    @api.depends(
        "l10n_ve_control_number",
        "country_code",
        "move_type",
        "journal_id",
        "journal_id.l10n_ve_emission_medium",
        "journal_id.l10n_ve_invoice_section_id",
        "journal_id.l10n_ve_credit_note_section_id",
        "journal_id.l10n_ve_debit_note_section_id",
        "debit_origin_id",
    )
    def _compute_l10n_ve_control_number_placeholder(self):
        ve = self.env.ref("base.ve").code
        for move in self:
            move.l10n_ve_control_number_placeholder = False
            if move.country_code != ve:
                continue
            if (move.l10n_ve_control_number or "").strip():
                continue
            if move.move_type not in ("out_invoice", "out_refund"):
                continue
            journal = move.journal_id
            if not journal or journal.type != "sale":
                continue
            if journal.l10n_ve_emission_medium != "free":
                continue
            section = move._l10n_ve_journal_fiscal_book_section()
            if not section:
                continue
            book = section.book_id
            move.l10n_ve_control_number_placeholder = (
                book.l10n_ve_peek_next_formatted(section) or False
            )

    @api.depends(
        "l10n_ve_control_number",
        "l10n_ve_control_number_placeholder",
        "country_code",
        "state",
        "move_type",
        "l10n_ve_journal_emission_medium",
        "l10n_ve_on_behalf_of_third_party",
        "journal_id",
        "journal_id.type",
    )
    def _compute_l10n_ve_show_control_number_ui(self):
        for move in self:
            move.l10n_ve_show_control_number_ui = move._l10n_ve_should_show_control_number_ui()

    def _l10n_ve_should_show_control_number_ui(self):
        self.ensure_one()
        ve = self.env.ref("base.ve").code
        if self.country_code != ve:
            return False
        if self.move_type not in ("out_invoice", "out_refund", "in_invoice"):
            return False
        if self.move_type in ("out_invoice", "out_refund"):
            if (
                self.l10n_ve_journal_emission_medium == "fiscal_machine"
                and not self.l10n_ve_on_behalf_of_third_party
            ):
                return False
        if (self.l10n_ve_control_number or "").strip():
            return True
        if self.l10n_ve_control_number_placeholder:
            return True
        if (
            self.state == "draft"
            and self.move_type in ("out_invoice", "out_refund")
            and self.l10n_ve_journal_emission_medium == "free"
            and self.journal_id
            and self.journal_id.type == "sale"
        ):
            return True
        if self.move_type == "in_invoice" and self.state == "draft":
            return True
        if (
            self.state == "draft"
            and self.move_type in ("out_invoice", "out_refund")
            and self.l10n_ve_journal_emission_medium
            and self.l10n_ve_journal_emission_medium != "free"
            and (
                self.l10n_ve_journal_emission_medium != "fiscal_machine"
                or self.l10n_ve_on_behalf_of_third_party
            )
        ):
            return True
        return False

    def _generate_control_number(self):
        self.ensure_one()
        if self.l10n_ve_control_number:
            return

        journal = self.journal_id
        if not journal or journal.type != "sale":
            return
        if journal.l10n_ve_emission_medium != "free":
            return

        section = self._l10n_ve_journal_fiscal_book_section()
        if section:
            book = section.book_id
            with self.env.cr.savepoint():
                formatted = book.l10n_ve_allocate_correlative(section, self)
                self.write({"l10n_ve_control_number": formatted})
            return

        raise ValidationError(
            _(
                "Configure en el diario de ventas los tramos del talonario "
                "(facturas, notas de débito y notas de crédito) para poder asignar "
                "el correlativo y el número de control SENIAT."
            )
        )

    @api.constrains("invoice_date", "invoice_date_due", "move_type")
    def _check_l10n_ve_invoice_date_due_not_before_invoice_date(self):
        for move in self:
            if move.move_type not in (
                "out_invoice",
                "out_refund",
                "in_invoice",
                "in_refund",
            ):
                continue
            if not move.invoice_date or not move.invoice_date_due:
                continue
            if move.invoice_date_due < move.invoice_date:
                raise ValidationError(
                    _(
                        "La fecha de vencimiento no puede ser anterior a la fecha "
                        "de la factura."
                    )
                )

    @api.constrains("l10n_ve_control_number", "journal_id")
    def _check_l10n_ve_control_number_journal_unique(self):
        for move in self:
            if not move.l10n_ve_control_number:
                continue
            if move.move_type not in ("out_invoice", "out_refund"):
                continue
            move._check_control_number_unique()

    def _check_control_number_unique(self):
        self.ensure_one()
        if not self.l10n_ve_control_number:
            return

        if self.move_type not in ("out_invoice", "out_refund"):
            return

        domain = [
            ("l10n_ve_control_number", "=", self.l10n_ve_control_number),
            ("company_id", "=", self.company_id.id),
            ("journal_id", "=", self.journal_id.id),
            ("id", "!=", self.id),
        ]

        existing = self.search(domain, limit=1)
        if existing:
            raise ValidationError(
                _(
                    "El número de control '%(num)s' ya está asignado a otro "
                    "documento en el diario '%(journal)s' (empresa %(company)s)."
                )
                % {
                    "num": self.l10n_ve_control_number,
                    "journal": self.journal_id.display_name,
                    "company": self.company_id.name,
                }
            )

        self._check_control_number_not_inferior()

    def _l10n_ve_control_number_parts(self, control_number):
        if not control_number:
            return ("00", 0)
        s = (control_number or "").strip()
        m = re.match(r"^(\d{2})-(\d+)$", s)
        if m:
            return (m.group(1), int(m.group(2)))
        digits = "".join(c for c in s if c.isdigit())
        return ("00", int(digits) if digits else 0)

    def _extract_control_number_numeric(self, control_number):
        return self._l10n_ve_control_number_parts(control_number)[1]

    def _check_control_number_not_inferior(self):
        self.ensure_one()
        if not self.l10n_ve_control_number:
            return

        current_est, current_seq = self._l10n_ve_control_number_parts(
            self.l10n_ve_control_number
        )
        max_seq = None
        reference = self.browse()
        for other in self.search(
            [
                ("l10n_ve_control_number", "!=", False),
                ("company_id", "=", self.company_id.id),
                ("move_type", "=", self.move_type),
                ("id", "!=", self.id),
            ]
        ):
            est, seq = self._l10n_ve_control_number_parts(other.l10n_ve_control_number)
            if est != current_est:
                continue
            if max_seq is None or seq > max_seq:
                max_seq = seq
                reference = other
        if not reference:
            return
        # if current_seq < max_seq:
        #     raise ValidationError(
        #         _(
        #             "El número de control '%(cur)s' es inferior al último número de "
        #             "control asignado '%(ref)s' en la compañía '%(company)s'. No se "
        #             "permite asignar un número de control anterior al último "
        #             "utilizado."
        #         )
        #         % {
        #             "cur": self.l10n_ve_control_number,
        #             "ref": reference.l10n_ve_control_number,
        #             "company": self.company_id.name,
        #         }
        #     )

    sale_tax_data = fields.Json(
        string="Datos de Impuestos para Libro de Ventas",
        compute="_compute_sale_tax_data",
        store=True,
        help=(
            "Estructura: {tax_group_id: {'base': X, 'amount': Y, "
            "'tax_type': 'exempt|reduced|general|extend'}}"
        ),
    )

    purchase_tax_data = fields.Json(
        string="Datos de Impuestos para Libro de Compras",
        compute="_compute_purchase_tax_data",
        store=True,
        help=(
            "Estructura: {tax_group_id: {'base': X, 'amount': Y, "
            "'tax_type': 'exempt|reduced|general|extend'}}"
        ),
    )

    @api.depends("tax_totals", "move_type", "state", "company_id")
    def _compute_sale_tax_data(self):  # noqa: C901
        for move in self:
            if move.state != "posted" or move.move_type not in [
                "out_invoice",
                "out_refund",
            ]:
                move.sale_tax_data = {}
                continue

            if not move.company_id:
                move.sale_tax_data = {}
                continue

            tax_data = {}
            tax_totals = move.tax_totals or {}
            multiplier = -1 if move.move_type == "out_refund" else 1

            company = move.company_id
            tax_config = {}
            if hasattr(company, "exent_aliquot_sale") and company.exent_aliquot_sale:
                tax_config["exempt"] = company.exent_aliquot_sale.tax_group_id.id
            if (
                hasattr(company, "reduced_aliquot_sale")
                and company.reduced_aliquot_sale
            ):
                tax_config["reduced"] = company.reduced_aliquot_sale.tax_group_id.id
            if (
                hasattr(company, "general_aliquot_sale")
                and company.general_aliquot_sale
            ):
                tax_config["general"] = company.general_aliquot_sale.tax_group_id.id
            if hasattr(company, "extend_aliquot_sale") and company.extend_aliquot_sale:
                tax_config["extend"] = company.extend_aliquot_sale.tax_group_id.id

            subtotals = tax_totals.get("subtotals", [])
            for subtotal in subtotals:
                if not isinstance(subtotal, dict):
                    continue
                tax_groups = subtotal.get("tax_groups", [])
                if not isinstance(tax_groups, list):
                    continue
                for tax_info in tax_groups:
                    if not isinstance(tax_info, dict):
                        continue
                    tax_group_id = tax_info.get("id")
                    if not tax_group_id:
                        continue

                    tax_type = None
                    for ttype, tg_id in tax_config.items():
                        if tg_id == tax_group_id:
                            tax_type = ttype
                            break

                    base_amount = (
                        tax_info.get(
                            "base_amount", tax_info.get("base_amount_currency", 0.0)
                        )
                        * multiplier
                    )
                    tax_amount = (
                        tax_info.get(
                            "tax_amount", tax_info.get("tax_amount_currency", 0.0)
                        )
                        * multiplier
                    )
                    tax_data[str(tax_group_id)] = {
                        "base": base_amount,
                        "amount": tax_amount,
                        "tax_type": tax_type,
                    }

            total_taxed = 0.0
            for tax_group_id_str, tax_info in tax_data.items():
                if tax_group_id_str.startswith("_"):
                    continue
                if isinstance(tax_info, dict) and tax_info.get("tax_type") != "exempt":
                    total_taxed += tax_info.get("base", 0.0) + tax_info.get(
                        "amount", 0.0
                    )

            tax_data["_total_taxed"] = total_taxed
            if tax_totals:
                base_untaxed = tax_totals.get(
                    "base_amount",
                    tax_totals.get(
                        "base_amount_currency", tax_totals.get("amount_untaxed", 0.0)
                    ),
                )
                tax_data["_total_untaxed"] = base_untaxed * multiplier
            else:
                tax_data["_total_untaxed"] = 0.0

            move.sale_tax_data = tax_data

    def get_sale_tax_values_by_type(self, tax_type="general"):
        """
        Obtiene los valores de impuestos almacenados por tipo de alícuota.

        Args:
            tax_type: 'exempt', 'reduced', 'general', 'extend'

        Returns:
            dict: {'base': X, 'amount': Y} o {'base': 0.0, 'amount': 0.0}
        """
        self.ensure_one()
        if not self.sale_tax_data:
            return {"base": 0.0, "amount": 0.0}

        company = self.company_id
        tax_config = {}
        if hasattr(company, "exent_aliquot_sale") and company.exent_aliquot_sale:
            tax_config["exempt"] = company.exent_aliquot_sale.tax_group_id.id
        if hasattr(company, "reduced_aliquot_sale") and company.reduced_aliquot_sale:
            tax_config["reduced"] = company.reduced_aliquot_sale.tax_group_id.id
        if hasattr(company, "general_aliquot_sale") and company.general_aliquot_sale:
            tax_config["general"] = company.general_aliquot_sale.tax_group_id.id
        if hasattr(company, "extend_aliquot_sale") and company.extend_aliquot_sale:
            tax_config["extend"] = company.extend_aliquot_sale.tax_group_id.id

        tax_group_id = tax_config.get(tax_type)
        if not tax_group_id:
            return {"base": 0.0, "amount": 0.0}

        return self.sale_tax_data.get(tax_group_id, {"base": 0.0, "amount": 0.0})

    @api.depends("tax_totals", "move_type", "state", "company_id")
    def _compute_purchase_tax_data(self):  # noqa: C901
        for move in self:
            if move.state != "posted" or move.move_type not in [
                "in_invoice",
                "in_refund",
            ]:
                move.purchase_tax_data = {}
                continue

            if not move.company_id:
                move.purchase_tax_data = {}
                continue

            tax_data = {}
            tax_totals = move.tax_totals or {}
            multiplier = -1 if move.move_type == "in_refund" else 1

            company = move.company_id
            tax_config = {}
            if (
                hasattr(company, "exent_aliquot_purchase")
                and company.exent_aliquot_purchase
            ):
                tax_config["exempt"] = company.exent_aliquot_purchase.tax_group_id.id
            if (
                hasattr(company, "reduced_aliquot_purchase")
                and company.reduced_aliquot_purchase
            ):
                tax_config["reduced"] = company.reduced_aliquot_purchase.tax_group_id.id
            if (
                hasattr(company, "general_aliquot_purchase")
                and company.general_aliquot_purchase
            ):
                tax_config["general"] = company.general_aliquot_purchase.tax_group_id.id
            if (
                hasattr(company, "extend_aliquot_purchase")
                and company.extend_aliquot_purchase
            ):
                tax_config["extend"] = company.extend_aliquot_purchase.tax_group_id.id

            subtotals = tax_totals.get("subtotals", [])
            for subtotal in subtotals:
                if not isinstance(subtotal, dict):
                    continue
                tax_groups = subtotal.get("tax_groups", [])
                if not isinstance(tax_groups, list):
                    continue
                for tax_info in tax_groups:
                    if not isinstance(tax_info, dict):
                        continue
                    tax_group_id = tax_info.get("id")
                    if not tax_group_id:
                        continue

                    tax_type = None
                    for ttype, tg_id in tax_config.items():
                        if tg_id == tax_group_id:
                            tax_type = ttype
                            break

                    base_amount = (
                        tax_info.get(
                            "base_amount", tax_info.get("base_amount_currency", 0.0)
                        )
                        * multiplier
                    )
                    tax_amount = (
                        tax_info.get(
                            "tax_amount", tax_info.get("tax_amount_currency", 0.0)
                        )
                        * multiplier
                    )
                    tax_data[str(tax_group_id)] = {
                        "base": base_amount,
                        "amount": tax_amount,
                        "tax_type": tax_type,
                    }

            total_taxed = 0.0
            for tax_group_id_str, tax_info in tax_data.items():
                if tax_group_id_str.startswith("_"):
                    continue
                if isinstance(tax_info, dict) and tax_info.get("tax_type") != "exempt":
                    tax_amount = tax_info.get("amount", 0.0)
                    if tax_amount != 0.0:
                        total_taxed += tax_info.get("base", 0.0) + tax_amount

            tax_data["_total_taxed"] = total_taxed
            if tax_totals:
                base_untaxed = tax_totals.get(
                    "base_amount",
                    tax_totals.get(
                        "base_amount_currency", tax_totals.get("amount_untaxed", 0.0)
                    ),
                )
                tax_data["_total_untaxed"] = base_untaxed * multiplier
            else:
                tax_data["_total_untaxed"] = 0.0

            move.purchase_tax_data = tax_data

    l10n_ve_inverse_rate = fields.Float(
        string="Tasa de Cambio Inversa",
        compute="_compute_l10n_ve_inverse_rate",
        store=True,
        help=(
            "Tasa de cambio inversa (inverse_rate) de la moneda de la factura "
            "para la fecha de la factura"
        ),
    )
    l10n_ve_currency_rate_outdated = fields.Boolean(
        string="Tasa de cambio desactualizada",
        compute="_compute_l10n_ve_currency_rate_outdated",
    )

    @api.depends(
        "state",
        "move_type",
        "currency_id",
        "company_currency_id",
        "invoice_currency_rate",
        "expected_currency_rate",
        "invoice_date",
    )
    def _compute_l10n_ve_currency_rate_outdated(self):
        for move in self:
            if (
                move.state != "draft"
                or move.move_type == "entry"
                or not move.currency_id
                or move.currency_id == move.company_currency_id
            ):
                move.l10n_ve_currency_rate_outdated = False
                continue
            move.l10n_ve_currency_rate_outdated = bool(
                float_compare(
                    move.invoice_currency_rate,
                    move.expected_currency_rate,
                    precision_digits=6,
                )
            )

    @api.depends("currency_id", "date", "company_id")
    def _compute_l10n_ve_inverse_rate(self):
        for move in self:
            if not move.currency_id or not move.date or not move.company_id:
                move.l10n_ve_inverse_rate = 0.0
                continue

            if move.currency_id == move.company_id.currency_id:
                move.l10n_ve_inverse_rate = 1.0
                continue

            currency_rate = self.env["res.currency.rate"].search(
                [
                    ("currency_id", "=", move.currency_id.id),
                    ("name", "<=", move.date),
                    ("company_id", "=", move.company_id.id),
                ],
                order="name desc",
                limit=1,
            )
            if currency_rate and currency_rate.rate and currency_rate.rate != 0.0:
                move.l10n_ve_inverse_rate = 1.0 / currency_rate.rate
            else:
                move.l10n_ve_inverse_rate = 0.0

    def _get_name_invoice_report(self):
        self.ensure_one()
        if self.company_id.account_fiscal_country_id.code == "VE":
            return "l10n_ve_seniat.report_invoice_document"
        return super()._get_name_invoice_report()

    @api.depends_context("lang")
    @api.depends(
        "invoice_line_ids.currency_rate",
        "invoice_line_ids.tax_base_amount",
        "invoice_line_ids.tax_line_id",
        "invoice_line_ids.price_total",
        "invoice_line_ids.price_subtotal",
        "invoice_payment_term_id",
        "partner_id",
        "currency_id",
    )
    def _compute_tax_totals(self):
        res = super()._compute_tax_totals()
        for move in self:
            if move.country_code != "VE" or not move.tax_totals:
                continue
            move.tax_totals["same_tax_base"] = False
            for subtotal in move.tax_totals.get("subtotals", []):
                for tax_group in subtotal.get("tax_groups", []):
                    if tax_group.get("display_base_amount_currency") is False:
                        tax_group["display_base_amount_currency"] = tax_group.get(
                            "base_amount_currency", 0.0
                        )
                    if tax_group.get("display_base_amount") in (False, None):
                        tax_group["display_base_amount"] = tax_group.get(
                            "base_amount", 0.0
                        )
        return res

    def action_send_and_print(self):
        for move in self:
            if move._l10n_ve_block_invoice_pdf_contingency():
                raise UserError(
                    _(
                        "En contingencia no esta permitido imprimir ni enviar el documento "
                        "desde esta acción."
                    )
                )
        return super().action_send_and_print()

    def action_invoice_sent(self):
        self.ensure_one()
        if self._l10n_ve_block_invoice_pdf_contingency():
            raise UserError(
                _(
                    "En contingencia no esta permitido enviar el documento por correo."
                )
            )
        return super().action_invoice_sent()

    def _l10n_ve_allows_invoice_pdf_download(self):
        self.ensure_one()
        if self.state != "posted":
            return False
        medium = self.l10n_ve_journal_emission_medium
        if medium != "free":
            return False
        if self.journal_id.l10n_ve_free_form_print_medium == "continuous":
            return False
        if not self.l10n_ve_invoice_original_printed:
            return False
        return True

    def _l10n_ve_allows_invoice_portal_view(self):
        self.ensure_one()
        if self.state != "posted":
            return False
        if self.country_code != "VE" or self.move_type not in ("out_invoice", "out_refund"):
            return True
        if self._l10n_ve_block_invoice_pdf_contingency():
            return False
        if self._l10n_ve_blocking_invoice_report_before_digital_sent():
            return False
        return True

    def _l10n_ve_show_download_pdf_action(self):
        self.ensure_one()
        if self.country_code != "VE":
            return True
        if self.move_type not in ("out_invoice", "out_refund"):
            return True
        return self._l10n_ve_allows_invoice_pdf_download()

    def get_extra_print_items(self):
        ve_invoices = self.filtered(
            lambda move: move.country_code == "VE"
            and move.move_type in ("out_invoice", "out_refund")
        )
        if ve_invoices and any(
            not move._l10n_ve_show_download_pdf_action() for move in ve_invoices
        ):
            return []
        return super().get_extra_print_items()

    def _l10n_ve_check_invoice_print_allowed(self):
        for move in self:
            if move.country_code != "VE":
                continue
            if move.move_type not in ("out_invoice", "out_refund"):
                continue
            if move.state == "cancel":
                raise UserError(_("No se puede imprimir una factura anulada."))
            if move.state != "posted":
                raise UserError(_("Debe confirmar la factura antes de imprimirla."))

    def preview_invoice(self):
        self._l10n_ve_check_invoice_print_allowed()
        self.ensure_one()
        if self._l10n_ve_block_invoice_pdf_contingency():
            raise UserError(
                _(
                    "En contingencia no esta permitido abrir la vista previa del documento."
                )
            )
        return super().preview_invoice()

    def _l10n_ve_sanitize_pdf_filename_part(self, value):
        value = (value or "").strip()
        return re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("._")

    def _l10n_ve_is_ve_customer_invoice_pdf(self):
        self.ensure_one()
        return (
            self.country_code == "VE"
            and self.move_type in ("out_invoice", "out_refund")
        )

    def _l10n_ve_get_invoice_pdf_basename(self):
        self.ensure_one()
        invoice_name = self._l10n_ve_sanitize_pdf_filename_part(self.name)
        if not invoice_name or invoice_name == "/":
            invoice_name = str(self.id)
        vat = self._l10n_ve_sanitize_pdf_filename_part(self.partner_id.vat)
        if vat:
            return f"{invoice_name}_{vat}"
        return invoice_name

    def _get_report_base_filename(self):
        self.ensure_one()
        if self._l10n_ve_is_ve_customer_invoice_pdf():
            return self._l10n_ve_get_invoice_pdf_basename()
        return super()._get_report_base_filename()

    def _get_invoice_report_filename(self, extension="pdf"):
        self.ensure_one()
        if self._l10n_ve_is_ve_customer_invoice_pdf():
            return f"{self._l10n_ve_get_invoice_pdf_basename()}.{extension}"
        return super()._get_invoice_report_filename(extension=extension)

    def _get_invoice_proforma_pdf_report_filename(self):
        self.ensure_one()
        if self._l10n_ve_is_ve_customer_invoice_pdf():
            return self._get_invoice_report_filename()
        return super()._get_invoice_proforma_pdf_report_filename()

    def _get_invoice_legal_documents(self, filetype, allow_fallback=False):
        document = super()._get_invoice_legal_documents(
            filetype, allow_fallback=allow_fallback
        )
        if (
            document
            and filetype == "pdf"
            and self._l10n_ve_is_ve_customer_invoice_pdf()
        ):
            document["filename"] = self._get_invoice_report_filename()
        return document

    def _l10n_ve_get_free_form_continuous_print_action(self):
        self.ensure_one()
        return False

    def _l10n_ve_should_attach_first_free_form_print_pdf(self):
        self.ensure_one()
        return (
            self.country_code == "VE"
            and self.move_type in ("out_invoice", "out_refund")
            and self.state == "posted"
            and self.l10n_ve_journal_emission_medium == "free"
            and not self.l10n_ve_invoice_original_printed
            and not self.invoice_pdf_report_id
        )

    def _l10n_ve_attach_invoice_pdf_report(self, pdf_content):
        self.ensure_one()
        if self.invoice_pdf_report_id:
            return
        filename = self._get_invoice_report_filename()
        if not filename:
            filename = f"{(self.name or 'invoice').replace('/', '_')}.pdf"
        attachment = self.env["ir.attachment"].sudo().create(
            {
                "name": filename,
                "raw": pdf_content,
                "mimetype": "application/pdf",
                "res_model": self._name,
                "res_id": self.id,
                "res_field": "invoice_pdf_report_file",
            }
        )
        self.message_main_attachment_id = attachment
        self.invalidate_recordset(["invoice_pdf_report_id", "invoice_pdf_report_file"])

    def action_print_pdf(self):
        self._l10n_ve_check_invoice_print_allowed()
        self.ensure_one()
        if (
            self.company_id.account_fiscal_country_id.code == "VE"
            and self.move_type in ("out_invoice", "out_refund")
            and self.l10n_ve_journal_emission_medium == "free"
            and self.journal_id.l10n_ve_free_form_print_medium == "continuous"
        ):
            action = self._l10n_ve_get_free_form_continuous_print_action()
            if action:
                if action.get("type") == "ir.actions.client":
                    return action
                return self._get_action_with_base_document_layout_configurator(
                    action
                )
            raise UserError(
                _(
                    "El diario está configurado para papel continuo. Instale el módulo "
                    "«l10n_ve_invoice_escp» para imprimir la factura en formato ESC/P por "
                    "USB (WebUSB), o cambie la impresión en forma libre a PDF en el diario."
                )
            )
        return super(
            AccountMove, self.with_context(l10n_ve_invoice=True)
        ).action_print_pdf()

    l10n_ve_lock_credit_debit_journal = fields.Boolean(
        compute="_compute_l10n_ve_lock_credit_debit_journal",
    )

    @api.depends(
        "move_type",
        "debit_origin_id",
        "company_id.account_fiscal_country_id",
    )
    def _compute_l10n_ve_lock_credit_debit_journal(self):
        for move in self:
            move.l10n_ve_lock_credit_debit_journal = (
                move.company_id.account_fiscal_country_id.code == "VE"
                and (
                    move.move_type in ("out_refund", "in_refund")
                    or bool(move.debit_origin_id)
                )
            )

    def _l10n_ve_sync_journal_with_origin_from_create(self):
        for move in self:
            if move.company_id.account_fiscal_country_id.code != "VE":
                continue
            origin = move.reversed_entry_id or move.debit_origin_id
            if not origin:
                continue
            updates = {}
            if move.journal_id != origin.journal_id:
                updates["journal_id"] = origin.journal_id.id
            if move.partner_id != origin.partner_id:
                updates["partner_id"] = origin.partner_id.id
            if updates:
                move.with_context(
                    l10n_ve_skip_credit_debit_journal_lock=True
                ).write(updates)

    def action_reverse(self):
        self._l10n_ve_check_credit_debit_allowed()
        return super().action_reverse()

    def action_debit_note(self):
        self._l10n_ve_check_credit_debit_allowed()
        return super().action_debit_note()

    def _l10n_ve_check_credit_debit_journal_matches_origin(self):
        for move in self:
            if move.company_id.account_fiscal_country_id.code != "VE":
                continue
            origin = move.reversed_entry_id or move.debit_origin_id
            if not origin:
                continue
            if move.journal_id != origin.journal_id:
                raise UserError(
                    _(
                        "No puede confirmar esta nota de crédito o débito: el diario "
                        "(%(journal)s) debe ser el mismo que el de la factura de origen "
                        "(%(origin_journal)s).",
                        journal=move.journal_id.display_name,
                        origin_journal=origin.journal_id.display_name,
                    )
                )
            if move.partner_id != origin.partner_id:
                raise UserError(
                    _(
                        "No puede confirmar esta nota de crédito o débito: el contacto "
                        "debe ser el mismo que el de la factura de origen "
                        "(%(partner)s).",
                        partner=origin.partner_id.display_name,
                    )
                )

    def _l10n_ve_check_credit_note_products_and_labels(self):
        Product = self.env["product.product"].sudo()
        for move in self:
            if move.company_id.account_fiscal_country_id.code != "VE":
                continue
            if move.move_type not in ("out_refund", "in_refund"):
                continue
            origin = move.reversed_entry_id
            if not origin:
                continue
            origin_product_ids = set(
                origin.invoice_line_ids.filtered(
                    lambda l: l.display_type == "product" and l.product_id
                ).mapped("product_id").ids
            )
            for line in move.invoice_line_ids:
                if line.display_type == "line_section":
                    continue
                if line.display_type == "line_note":
                    move._l10n_ve_credit_note_line_check_description_not_product_name(
                        line, Product
                    )
                    continue
                if line.product_id:
                    if line.product_id.id not in origin_product_ids:
                        raise UserError(
                            _(
                                "En una nota de crédito (VE) no puede incluirse el "
                                "producto «%(product)s» porque no está en la factura "
                                "original %(origin)s.",
                                product=line.product_id.display_name,
                                origin=origin.display_name,
                            )
                        )
                else:
                    move._l10n_ve_credit_note_line_check_description_not_product_name(
                        line, Product
                    )

    def _l10n_ve_credit_note_line_check_description_not_product_name(self, line, product_model):
        text = html2plaintext(line.name or "").strip()
        if not text:
            return
        if product_model.search([("name", "=", text)], limit=1):
            raise UserError(
                _(
                    "En una nota de crédito (VE), una línea sin producto no puede usar "
                    "la descripción «%(text)s» porque coincide con el nombre de un "
                    "producto existente.",
                    text=text,
                )
            )

    def l10n_ve_report_exchange_rate_display(self):
        self.ensure_one()
        if self.currency_id == self.company_currency_id:
            return False
        if not self.l10n_ve_inverse_rate:
            return False
        amount = formatLang(
            self.env,
            self.l10n_ve_inverse_rate,
            digits=min(2, self.company_currency_id.decimal_places),
        )
        symbol = (self.company_currency_id.symbol or "Bs").strip()
        return f"{amount} {symbol}"

    def l10n_ve_report_invoice_lines(self):
        self.ensure_one()
        lines = self.invoice_line_ids.sorted(key=lambda line: (line.sequence, line.id))
        if self.company_id.account_fiscal_country_id.code != "VE":
            return lines
        disc = self.company_id.sale_discount_product_id
        if not disc:
            return lines

        def _is_discount_product_line(line):
            return line.display_type == "product" and line.product_id == disc

        discount_lines = lines.filtered(_is_discount_product_line)
        if not discount_lines:
            return lines
        return lines.filtered(lambda line: not _is_discount_product_line(line)) + discount_lines
