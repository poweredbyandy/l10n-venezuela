from odoo import api, models

L10N_VE_SKIP_STOCK_PICKING_UNBIND = "l10n_ve_skip_stock_picking_unbind"


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get(L10N_VE_SKIP_STOCK_PICKING_UNBIND):
            records._l10n_ve_unbind_stock_picking_report_bindings()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get(L10N_VE_SKIP_STOCK_PICKING_UNBIND):
            self._l10n_ve_unbind_stock_picking_report_bindings()
        return res

    def _l10n_ve_unbind_stock_picking_report_bindings(self):
        picking_model = self.env["ir.model"]._get("stock.picking")
        if not picking_model:
            return
        to_clear = self.sudo().filtered(
            lambda action: action.binding_model_id == picking_model
            and action.binding_type == "report"
        )
        if to_clear:
            to_clear.with_context(**{L10N_VE_SKIP_STOCK_PICKING_UNBIND: True}).write(
                {"binding_model_id": False}
            )

    @api.model
    def _l10n_ve_unbind_all_stock_picking_report_bindings(self):
        picking_model = self.env["ir.model"]._get("stock.picking")
        if not picking_model:
            return
        self.env["ir.actions.server"].sudo().search(
            [
                ("binding_model_id", "=", picking_model.id),
                ("binding_type", "=", "report"),
            ]
        )._l10n_ve_unbind_stock_picking_report_bindings()
