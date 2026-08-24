from odoo import _, models
from odoo.exceptions import UserError


class ProductProduct(models.Model):
    _inherit = "product.product"

    def write(self, vals):
        if (
            "default_code" in vals
            and not self.env.context.get("l10n_ve_skip_product_default_code_lock")
            and not self.env.user.has_group(
                "l10n_ve_seniat.group_l10n_ve_override_locked_master_data"
            )
        ):
            tmpl_model = self.env["product.template"]
            if tmpl_model._l10n_ve_fiscal_locks_apply():
                for product in self:
                    if product.product_tmpl_id._l10n_ve_has_done_stock_moves():
                        raise UserError(
                            _(
                                "Cannot change the internal reference of product “%s” "
                                "after it has completed stock moves. Ask a settings "
                                "administrator."
                            )
                            % (product.product_tmpl_id.display_name,)
                        )
        return super().write(vals)
