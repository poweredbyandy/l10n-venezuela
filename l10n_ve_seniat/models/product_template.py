# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.constrains("taxes_id", "supplier_taxes_id")
    def _l10n_ve_check_exactly_one_tax_per_use(self):
        ve_country = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve_country:
            return
        for tmpl in self:
            company = tmpl.company_id or self.env.company
            if company.account_fiscal_country_id != ve_country:
                continue
            n_sale = len(tmpl.taxes_id)
            if n_sale != 1:
                raise ValidationError(
                    _(
                        'El producto "%(name)s" debe tener exactamente un impuesto de '
                        "ventas en compañías venezolanas (tiene %(n)d)."
                    )
                    % {"name": tmpl.display_name, "n": n_sale}
                )
            n_purchase = len(tmpl.supplier_taxes_id)
            if n_purchase != 1:
                raise ValidationError(
                    _(
                        'El producto "%(name)s" debe tener exactamente un impuesto de '
                        "compras en compañías venezolanas (tiene %(n)d)."
                    )
                    % {"name": tmpl.display_name, "n": n_purchase}
                )
