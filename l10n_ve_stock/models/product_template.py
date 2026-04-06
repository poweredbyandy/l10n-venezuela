from odoo import _, api, models
from odoo.exceptions import UserError, ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _l10n_ve_fiscal_locks_apply(self):
        country = self.env.company.account_fiscal_country_id
        return bool(country and country.code == "VE")

    def _l10n_ve_override_locked_product_fields(self):
        return self.env.user.has_group(
            "l10n_ve_seniat.group_l10n_ve_override_locked_master_data"
        )

    def _l10n_ve_has_done_stock_moves(self):
        self.ensure_one()
        variants = self.product_variant_ids
        if not variants:
            return False
        return bool(
            self.env["stock.move"]
            .sudo()
            .search(
                [
                    ("product_id", "in", variants.ids),
                    ("state", "=", "done"),
                ],
                limit=1,
            )
        )

    @api.constrains("taxes_id")
    def _l10n_ve_constrain_sales_tax_count(self):
        for tmpl in self:
            if (
                not tmpl._l10n_ve_fiscal_locks_apply()
                or tmpl._l10n_ve_override_locked_product_fields()
            ):
                continue
            if len(tmpl.taxes_id) != 1:
                raise ValidationError(
                    _(
                        "With Venezuelan fiscal localization, each product must have "
                        "exactly one sales tax."
                    )
                )

    def write(self, vals):
        if (
            self._l10n_ve_fiscal_locks_apply()
            and not self._l10n_ve_override_locked_product_fields()
        ):
            if "taxes_id" in vals:
                for tmpl in self:
                    if tmpl._l10n_ve_has_done_stock_moves():
                        raise UserError(
                            _(
                                "Cannot change sales taxes on product “%s” after it has "
                                "completed stock moves. Ask a settings administrator."
                            )
                            % (tmpl.display_name,)
                        )
            if "default_code" in vals:
                for tmpl in self:
                    if tmpl._l10n_ve_has_done_stock_moves():
                        raise UserError(
                            _(
                                "Cannot change the internal reference of product “%s” "
                                "after it has completed stock moves. Ask a settings "
                                "administrator."
                            )
                            % (tmpl.display_name,)
                        )
        return super().write(vals)
