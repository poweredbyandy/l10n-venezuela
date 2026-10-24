# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.depends_context("lang")
    @api.depends(
        "order_line.price_subtotal",
        "currency_id",
        "company_id",
        "payment_term_id",
        "currency_rate",
    )
    def _compute_tax_totals(self):
        res = super()._compute_tax_totals()
        AccountTax = self.env["account.tax"]
        for order in self:
            if not order.tax_totals:
                continue
            order.tax_totals = AccountTax._account_currency_align_order_tax_totals(
                order,
                order.tax_totals,
            )
        return res
