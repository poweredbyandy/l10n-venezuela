from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import format_date

from odoo.addons.web.controllers.utils import clean_action


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_emission_medium = fields.Selection(
        selection=[
            ("free", "Forma libre (correlativo de talonario)"),
            ("contingency", "Contingencia"),
            ("fiscal_machine", "Máquina fiscal"),
            ("digital", "Facturación digital"),
        ],
        string="Medio de emisión",
        default="free",
        copy=False,
        help=(
            "Forma libre: asigna correlativo desde el talonario interno. "
            "Contingencia: no usa el talonario; el N° de control se indica en la "
            "factura antes de confirmar. Máquina fiscal y facturación digital: "
            "tampoco generan correlativo automático del talonario; el N° de control "
            "debe consignarse manualmente antes de confirmar."
        ),
    )

    l10n_ve_free_form_print_medium = fields.Selection(
        selection=[
            ("pdf", "PDF"),
            ("continuous", "Papel continuo (ESC/P USB)"),
        ],
        string="Impresión en forma libre",
        default="pdf",
        copy=False,
        help=(
            "Solo aplica con medio de emisión «Forma libre». "
            "PDF usa el informe estándar. "
            "Papel continuo requiere el módulo «l10n_ve_invoice_escp» e imprime "
            "la factura en formato ESC/P Epson por WebUSB."
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
        string="Código forma de pago fiscal",
        size=2,
        copy=False,
        help=(
            "Código numérico de forma de pago para máquina fiscal TFHKA (01–24). "
            "Se usa al enviar pagos en la impresión fiscal cuando el registro proviene "
            "de este diario."
        ),
    )

    l10n_ve_max_invoice_lines = fields.Integer(
        string="Máximo de líneas por factura (diario)",
        default=10,
        copy=False,
        help=(
            "Si el medio de emisión no es «Forma libre», al facturar desde ventas se "
            "parte el pedido en varias facturas cuando supera este número de líneas de "
            "producto. Con «Forma libre» y tramo de talonario configurado, se usa el "
            "máximo definido en el talonario."
        ),
    )
    l10n_ve_max_picking_lines = fields.Integer(
        string="Máximo de líneas por guía de despacho (diario)",
        default=10,
        copy=False,
        help=(
            "Si el medio de emisión no es «Forma libre», al confirmar el pedido se "
            "dividen los albaranes de salida que superen este número de movimientos de "
            "producto. Con «Forma libre» y talonario en el tramo del diario, se usa el "
            "máximo del talonario."
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
                        "El código forma de pago fiscal del diario "
                        "“%(journal)s” debe ser dos dígitos (ej.: 01)."
                    )
                    % {"journal": journal.display_name}
                )
            value = int(raw)
            if value < 1 or value > 24:
                raise ValidationError(
                    _(
                        "El código forma de pago fiscal del diario "
                        "“%(journal)s” debe estar entre 01 y 24."
                    )
                    % {"journal": journal.display_name}
                )

    @api.constrains("l10n_ve_emission_medium", "l10n_ve_free_form_print_medium")
    def _check_l10n_ve_free_form_print_medium(self):
        for journal in self:
            if (
                journal.l10n_ve_free_form_print_medium == "continuous"
                and journal.l10n_ve_emission_medium != "free"
            ):
                raise ValidationError(
                    _(
                        "El formato «Papel continuo» solo está permitido cuando "
                        "el medio de emisión del diario «%(journal)s» es "
                        "«Forma libre»."
                    )
                    % {"journal": journal.display_name}
                )

    @api.constrains("l10n_ve_max_invoice_lines", "l10n_ve_max_picking_lines")
    def _check_l10n_ve_journal_max_lines(self):
        for journal in self:
            if (
                journal.l10n_ve_max_invoice_lines is not None
                and journal.l10n_ve_max_invoice_lines < 1
            ):
                raise ValidationError(
                    _(
                        "El máximo de líneas por factura del diario «%(journal)s» debe "
                        "ser al menos 1."
                    )
                    % {"journal": journal.display_name}
                )
            if (
                journal.l10n_ve_max_picking_lines is not None
                and journal.l10n_ve_max_picking_lines < 1
            ):
                raise ValidationError(
                    _(
                        "El máximo de líneas por guía del diario «%(journal)s» debe "
                        "ser al menos 1."
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

    @api.model
    def _l10n_ve_seniat_ve_companies(self):
        return self.env.companies.filtered(
            lambda company: company.account_fiscal_country_id.code == "VE"
        )

    @api.model
    def _l10n_ve_seniat_current_month_bounds(self):
        today = fields.Date.context_today(self)
        return today.replace(day=1), today

    @api.model
    def _l10n_ve_seniat_overdue_unpaid_invoices_domain(self, companies, today=None):
        today = today or fields.Date.context_today(self)
        return [
            ("company_id", "in", companies.ids),
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "in", ("not_paid", "partial")),
            ("invoice_date_due", "<", today),
        ]

    @api.model
    def _l10n_ve_seniat_dispatch_guide_dashboard_available(self):
        if "stock.picking" not in self.env:
            return False
        picking_model = self.env["stock.picking"]
        return "l10n_ve_is_ve_country" in picking_model._fields and callable(
            getattr(
                picking_model,
                "_l10n_ve_dispatch_outgoing_moves_fully_invoiced",
                None,
            )
        )

    @api.model
    def _l10n_ve_seniat_unfactured_dispatch_guides(self, companies):
        if "stock.picking" not in self.env:
            return self.env["account.move"].browse(), False
        if not self._l10n_ve_seniat_dispatch_guide_dashboard_available():
            return self.env["stock.picking"].browse(), False

        candidates = self.env["stock.picking"].search(
            [
                ("company_id", "in", companies.ids),
                ("state", "=", "done"),
                ("picking_type_code", "=", "outgoing"),
            ]
        )
        unfactured = candidates.filtered(
            lambda picking: picking.l10n_ve_is_ve_country
            and not picking._l10n_ve_dispatch_outgoing_moves_fully_invoiced()
        )
        return unfactured, True

    @api.model
    def get_l10n_ve_invoice_dashboard(self):
        ve_companies = self._l10n_ve_seniat_ve_companies()
        if not ve_companies:
            return {"visible": False, "items": [], "month_label": ""}

        month_start, today = self._l10n_ve_seniat_current_month_bounds()
        move_domain_base = [
            ("company_id", "in", ve_companies.ids),
            ("state", "=", "posted"),
            ("invoice_date", ">=", month_start),
            ("invoice_date", "<=", today),
        ]
        Move = self.env["account.move"]
        invoice_count = Move.search_count(
            move_domain_base + [("move_type", "=", "out_invoice")]
        )
        credit_count = Move.search_count(
            move_domain_base + [("move_type", "=", "out_refund")]
        )
        overdue_count = Move.search_count(
            self._l10n_ve_seniat_overdue_unpaid_invoices_domain(ve_companies, today)
        )
        dispatch_guides, dispatch_available = (
            self._l10n_ve_seniat_unfactured_dispatch_guides(ve_companies)
        )

        items = []
        if dispatch_available:
            items.append(
                {
                    "key": "unfactured_dispatch_guides",
                    "label": _("Guías de despacho no facturadas"),
                    "count": len(dispatch_guides),
                    "show_month_label": False,
                }
            )
        items.extend(
            [
                {
                    "key": "posted_invoices_month",
                    "label": _("Facturas confirmadas (mes)"),
                    "count": invoice_count,
                    "show_month_label": True,
                },
                {
                    "key": "credit_notes_month",
                    "label": _("Notas de crédito (mes)"),
                    "count": credit_count,
                    "show_month_label": True,
                },
                {
                    "key": "overdue_unpaid_invoices",
                    "label": _("Facturas vencidas sin pagar"),
                    "count": overdue_count,
                    "show_month_label": False,
                },
            ]
        )
        return {
            "visible": True,
            "month_label": format_date(self.env, month_start, date_format="MMMM y"),
            "items": items,
            "dispatch_email": self._l10n_ve_seniat_dispatch_email_dashboard_data(
                dispatch_available
            ),
        }

    @api.model
    def _l10n_ve_seniat_dispatch_email_dashboard_data(self, dispatch_available):
        company = self.env.company
        if not dispatch_available:
            return {
                "available": False,
                "can_send": False,
                "last_sent_label": False,
            }
        last_sent_label = (
            company.l10n_ve_unfactured_dispatch_email_last_sent_label() or False
        )
        return {
            "available": True,
            "can_send": bool(
                (company.l10n_ve_unfactured_dispatch_email_recipient or "").strip()
            ),
            "last_sent_label": last_sent_label,
        }

    @api.model
    def action_l10n_ve_send_unfactured_dispatch_guides_email(self):
        company = self.env.company
        company._l10n_ve_send_unfactured_dispatch_guides_email()
        return self._l10n_ve_seniat_dispatch_email_dashboard_data(True) | {
            "message": _("Correo de guías no facturadas enviado correctamente."),
        }

    @api.model
    def action_l10n_ve_invoice_dashboard_open(self, key):
        ve_companies = self._l10n_ve_seniat_ve_companies()
        if not ve_companies:
            raise UserError(_("No hay compañías venezolanas activas."))

        month_start, today = self._l10n_ve_seniat_current_month_bounds()
        move_domain_base = [
            ("company_id", "in", ve_companies.ids),
            ("state", "=", "posted"),
            ("invoice_date", ">=", month_start),
            ("invoice_date", "<=", today),
        ]

        if key == "unfactured_dispatch_guides":
            dispatch_guides, dispatch_available = (
                self._l10n_ve_seniat_unfactured_dispatch_guides(ve_companies)
            )
            if not dispatch_available:
                raise UserError(
                    _("Las guías de despacho requieren el módulo de inventario SENIAT.")
                )
            action = self.env["ir.actions.actions"]._for_xml_id(
                "stock.action_picking_tree_all"
            )
            action.update(
                {
                    "name": _("Guías de despacho no facturadas"),
                    "domain": [("id", "in", dispatch_guides.ids)],
                    "context": {
                        **self.env.context,
                        "create": False,
                    },
                }
            )
            return clean_action(action, self.env)

        if key == "posted_invoices_month":
            action = self.env["ir.actions.actions"]._for_xml_id(
                "account.action_move_out_invoice"
            )
            action.update(
                {
                    "name": _("Facturas confirmadas (mes)"),
                    "domain": move_domain_base + [("move_type", "=", "out_invoice")],
                    "context": {
                        **self.env.context,
                        "create": False,
                        "default_move_type": "out_invoice",
                    },
                }
            )
            return clean_action(action, self.env)

        if key == "credit_notes_month":
            action = self.env["ir.actions.actions"]._for_xml_id(
                "account.action_move_out_refund_type"
            )
            action.update(
                {
                    "name": _("Notas de crédito (mes)"),
                    "domain": move_domain_base + [("move_type", "=", "out_refund")],
                    "context": {
                        **self.env.context,
                        "create": False,
                        "default_move_type": "out_refund",
                    },
                }
            )
            return clean_action(action, self.env)

        if key == "overdue_unpaid_invoices":
            action = self.env["ir.actions.actions"]._for_xml_id(
                "account.action_move_out_invoice"
            )
            action.update(
                {
                    "name": _("Facturas vencidas sin pagar"),
                    "domain": self._l10n_ve_seniat_overdue_unpaid_invoices_domain(
                        ve_companies, today
                    ),
                    "context": {
                        **self.env.context,
                        "create": False,
                        "default_move_type": "out_invoice",
                        "search_default_late": 1,
                        "search_default_posted": 1,
                    },
                }
            )
            return clean_action(action, self.env)

        raise UserError(_("Indicador de tablero no reconocido."))
