# Copyright 2026 Anderson Armeya
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("currency_rate_index_skip_sync"):
            return res
        if {"order_line", "currency_id", "date_order", "company_id"} & set(vals):
            self._currency_rate_index_refresh_currency_rate()
        return res

    def _currency_rate_index_refresh_currency_rate(self):
        orders = self.filtered(
            lambda order: order.company_id.currency_index_id
            and order.currency_id
            and order.currency_id != order.company_id.currency_id
            and order.state in ("draft", "sent", "to approve")
        )
        if orders:
            orders._compute_currency_rate()
