# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_base_line_grouping_key(self, base_line):
        res = super()._prepare_base_line_grouping_key(base_line)
        res["price_subtotal_currency"] = base_line["price_subtotal_currency"]
        return res

    @api.model
    def _prepare_base_line_for_taxes_computation(self, record, **kwargs):
        res = super()._prepare_base_line_for_taxes_computation(record, **kwargs)
        res["price_subtotal_currency"] = self._get_base_line_field_value_from_record(
            record, "price_subtotal_currency", kwargs, 0.0
        )
        return res
