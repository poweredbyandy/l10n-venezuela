from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import format_date

from odoo.addons.web.controllers.utils import clean_action


# pylint: disable=consider-merging-classes-inherited
class AccountJournal(models.Model):
    _inherit = "account.journal"

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
        return {
            "visible": True,
            "month_label": format_date(self.env, month_start, date_format="MMMM y"),
            "items": [
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
            ],
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
