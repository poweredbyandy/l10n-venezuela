from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.web.controllers.utils import clean_action


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model
    def _l10n_ve_seniat_unfactured_dispatch_guides(self, companies):
        enabled_companies = companies.filtered("l10n_ve_dispatch_guide_enabled")
        if not enabled_companies:
            return self.env["stock.picking"].browse(), False
        candidates = self.env["stock.picking"].search(
            [
                ("company_id", "in", enabled_companies.ids),
                ("state", "=", "done"),
                ("picking_type_code", "=", "outgoing"),
                ("l10n_ve_control_number", "!=", False),
                ("l10n_ve_control_number", "!=", ""),
            ]
        )
        unfactured = candidates.filtered(
            lambda picking: picking.l10n_ve_is_ve_country
            and not picking._l10n_ve_dispatch_outgoing_moves_fully_invoiced()
        )
        return unfactured, True

    @api.model
    def get_l10n_ve_invoice_dashboard(self):
        data = super().get_l10n_ve_invoice_dashboard()
        if not data.get("visible"):
            return data
        ve_companies = self._l10n_ve_seniat_ve_companies()
        dispatch_guides, dispatch_available = (
            self._l10n_ve_seniat_unfactured_dispatch_guides(ve_companies)
        )
        if not dispatch_available:
            return data
        items = list(data.get("items") or [])
        items.insert(
            0,
            {
                "key": "unfactured_dispatch_guides",
                "label": _("Guías de despacho no facturadas"),
                "count": len(dispatch_guides),
                "show_month_label": False,
            },
        )
        data["items"] = items
        return data

    @api.model
    def action_l10n_ve_invoice_dashboard_open(self, key):
        if key != "unfactured_dispatch_guides":
            return super().action_l10n_ve_invoice_dashboard_open(key)

        ve_companies = self._l10n_ve_seniat_ve_companies()
        dispatch_guides, dispatch_available = (
            self._l10n_ve_seniat_unfactured_dispatch_guides(ve_companies)
        )
        if not dispatch_available:
            raise UserError(
                _("Las guías de despacho requieren el módulo de inventario SENIAT.")
            )
        action = self.env["ir.actions.actions"]._for_xml_id(
            "l10n_ve_stock.action_l10n_ve_unfactured_dispatch_guides"
        )
        action.update(
            {
                "domain": [("id", "in", dispatch_guides.ids)],
                "context": {
                    **self.env.context,
                    "create": False,
                },
            }
        )
        return clean_action(action, self.env)
