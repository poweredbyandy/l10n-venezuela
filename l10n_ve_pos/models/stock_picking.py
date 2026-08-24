from odoo import api, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        order_id = self.env.context.get("l10n_ve_pos_order_id")
        if order_id:
            order = self.env["pos.order"].browse(order_id).exists()
            if order:
                records.write(
                    {
                        "pos_session_id": order.session_id.id,
                        "pos_order_id": order.id,
                        "origin": order.name,
                    }
                )
        return records
