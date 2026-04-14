# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def l10n_ve_report_line_description(self):
        self.ensure_one()
        name = (self.name or "").strip()
        product = self.product_id
        if not product:
            return name
        code = (product.default_code or "").strip()
        if not code:
            return name
        prefix = f"[{code}]"
        if name.startswith(prefix):
            rest = name[len(prefix) :].strip()
            return rest or (product.name or "")
        return name

    @api.constrains("discount", "order_id")
    def _l10n_ve_check_line_discount(self):
        prec = self.env["decimal.precision"].precision_get("Discount")
        for line in self:
            if line.display_type:
                continue
            if line.order_id.country_code != "VE":
                continue
            disc = line.discount or 0.0
            if float_compare(disc, 100.0, precision_digits=prec) >= 0:
                raise ValidationError(
                    _(
                        "No se permite un descuento del 100%% en la línea. "
                        'La línea "%(line)s" tiene %(discount)s%%.'
                    )
                    % {
                        "line": line.name or _("Sin nombre"),
                        "discount": disc,
                    }
                )

    @api.constrains(
        "price_unit", "product_id", "display_type", "order_id", "is_downpayment"
    )
    def _l10n_ve_check_line_unit_price(self):
        prec = self.env["decimal.precision"].precision_get("Product Price")
        for line in self:
            if line.display_type:
                continue
            if line.is_downpayment:
                continue
            if line.order_id.country_code != "VE":
                continue
            price = line.price_unit or 0.0
            if float_compare(price, 0.0, precision_digits=prec) <= 0:
                disc = line.order_id.company_id.sale_discount_product_id
                if line.product_id and line.product_id == disc:
                    continue
                raise ValidationError(
                    _(
                        "No se permiten líneas con precio menor o igual a cero. "
                        'La línea "%(line)s" tiene precio %(price)s. Use el asistente '
                        "Descuento en el pedido (producto de descuento de compañía) o "
                        "corrija el importe."
                    )
                    % {"line": line.name or _("Sin nombre"), "price": price}
                )

    @api.constrains("tax_id", "order_id")
    def _check_tax_single_required_ve(self):
        for line in self:
            if line.display_type:
                continue
            if line.order_id.state != "sale":
                continue
            if line.order_id.country_code != "VE":
                continue
            if len(line.tax_id) == 0:
                raise ValidationError(
                    _(
                        "No se puede quitar el impuesto de la línea '%s' en un pedido "
                        "confirmado. Cada línea debe tener exactamente un impuesto."
                    )
                    % (line.name or _("Sin nombre"))
                )
            if len(line.tax_id) > 1:
                tax_mapped = ", ".join(line.tax_id.mapped("name"))
                raise ValidationError(
                    _(
                        "No se puede asignar más de un impuesto a la línea '%s' en un "
                        "pedido confirmado. Cree una línea separada "
                        "para cada impuesto. "
                        "Impuestos actuales: %s"
                    )
                    % (line.name or _("Sin nombre"), tax_mapped)
                )
