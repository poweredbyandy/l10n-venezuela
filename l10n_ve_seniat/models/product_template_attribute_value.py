# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ProductTemplateAttributeValue(models.Model):
    _inherit = "product.template.attribute.value"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped("product_tmpl_id")._l10n_ve_check_sale_price_vs_cost()
        return records

    def write(self, vals):
        res = super().write(vals)
        if "price_extra" in vals:
            self.mapped("product_tmpl_id")._l10n_ve_check_sale_price_vs_cost()
        return res
