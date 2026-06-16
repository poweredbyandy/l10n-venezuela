# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class SaleOrderDiscount(models.TransientModel):
    _inherit = "sale.order.discount"

    def action_apply_discount(self):
        for wizard in self:
            if wizard.company_id.account_fiscal_country_id.code != "VE":
                continue
            if wizard.discount_type in ("sol_discount", "so_discount"):
                if (
                    float_compare(wizard.discount_percentage, 1.0, precision_digits=10)
                    >= 0
                ):
                    raise ValidationError(
                        _("No se permite un descuento global del 100%% en el pedido.")
                    )
            elif wizard.discount_type == "amount":
                order = wizard.sale_order_id
                if not order or not order.amount_total:
                    continue
                so_amount = order.amount_total
                if any(
                    tax.amount_type == "fixed"
                    for tax in order.order_line.tax_id.flatten_taxes_hierarchy()
                ):
                    fixed_taxes_amount = 0
                    for line in order.order_line:
                        taxes = line.tax_id.flatten_taxes_hierarchy()
                        for tax in taxes.filtered(lambda t: t.amount_type == "fixed"):
                            fixed_taxes_amount += tax.amount * line.product_uom_qty
                    so_amount -= fixed_taxes_amount
                if (
                    so_amount
                    and float_compare(
                        wizard.discount_amount,
                        so_amount,
                        precision_digits=wizard.currency_id.decimal_places,
                    )
                    >= 0
                ):
                    raise ValidationError(
                        _(
                            "No se permite un descuento del 100%% del importe del pedido."
                        )
                    )
        return super().action_apply_discount()

    def _prepare_discount_product_values(self):
        vals = super()._prepare_discount_product_values()
        company = self.company_id
        if company.account_fiscal_country_id.code != "VE":
            return vals
        sale_tax = company.account_sale_tax_id
        purchase_tax = company.account_purchase_tax_id
        if sale_tax:
            vals["taxes_id"] = [(6, 0, [sale_tax.id])]
        if purchase_tax:
            vals["supplier_taxes_id"] = [(6, 0, [purchase_tax.id])]
        return vals
