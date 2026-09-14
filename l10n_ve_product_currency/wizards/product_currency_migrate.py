from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nVeProductCurrencyMigrateWizard(models.TransientModel):
    _name = "l10n.ve.product.currency.migrate.wizard"
    _description = "Migrate Product Currencies"

    migrate_sale = fields.Boolean(
        string="Migrate Sales Price Currency",
        default=True,
    )
    migrate_cost = fields.Boolean(
        string="Migrate Cost Currency",
        default=False,
        help="Leave this disabled to keep the current cost currency used by PBA costs.",
    )
    sale_from_currency_id = fields.Many2one(
        "res.currency",
        string="Current Sales Price Currency",
    )
    sale_to_currency_id = fields.Many2one(
        "res.currency",
        string="Destination Sales Price Currency",
    )
    cost_from_currency_id = fields.Many2one(
        "res.currency",
        string="Current Cost Currency",
    )
    cost_to_currency_id = fields.Many2one(
        "res.currency",
        string="Destination Cost Currency",
    )

    def _check_migrate_currencies(self):
        self.ensure_one()
        if not self.migrate_sale and not self.migrate_cost:
            raise UserError(
                _("Enable at least one currency to migrate (sales price or cost).")
            )
        if self.migrate_sale:
            if not self.sale_from_currency_id or not self.sale_to_currency_id:
                raise UserError(
                    _(
                        "Select the current and destination currencies for the sales price."
                    )
                )
            if self.sale_from_currency_id == self.sale_to_currency_id:
                raise UserError(
                    _(
                        "The destination sales price currency must be different from the current one."
                    )
                )
        if self.migrate_cost:
            if not self.cost_from_currency_id or not self.cost_to_currency_id:
                raise UserError(
                    _("Select the current and destination currencies for the cost.")
                )
            if self.cost_from_currency_id == self.cost_to_currency_id:
                raise UserError(
                    _(
                        "The destination cost currency must be different from the current one."
                    )
                )

    def action_migrate(self):
        self.ensure_one()
        self._check_migrate_currencies()
        templates = self.env["product.template"].with_context(active_test=False).search(
            []
        )
        sale_updated = self.env["product.template"]
        cost_updated = self.env["product.template"]
        if self.migrate_sale:
            sale_updated = templates._l10n_ve_migrate_currency(
                self.sale_from_currency_id,
                self.sale_to_currency_id,
                kind="sale",
            )
        if self.migrate_cost:
            cost_updated = templates._l10n_ve_migrate_currency(
                self.cost_from_currency_id,
                self.cost_to_currency_id,
                kind="cost",
            )
        count = len(sale_updated | cost_updated)
        if not count:
            raise UserError(
                _("No products were found in the selected current currency.")
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Product currencies migrated"),
                "message": _("%s product(s) updated.") % count,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
