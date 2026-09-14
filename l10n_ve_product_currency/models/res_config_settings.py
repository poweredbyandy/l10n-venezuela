from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ve_product_currency_default_force_currency_id = fields.Many2one(
        "res.currency",
        string="Default Sales Price Currency",
        config_parameter="l10n_ve_product_currency.default_force_currency_id",
        help="If empty, new products use the company currency for the sales price.",
    )
    l10n_ve_product_currency_default_force_cost_currency_id = fields.Many2one(
        "res.currency",
        string="Default Cost Currency",
        config_parameter="l10n_ve_product_currency.default_force_cost_currency_id",
        help="If empty, new products use the company currency for the cost.",
    )

    def action_open_l10n_ve_product_currency_migrate(self):
        self.ensure_one()
        sale_from = self.l10n_ve_product_currency_default_force_currency_id
        cost_from = self.l10n_ve_product_currency_default_force_cost_currency_id
        if not sale_from:
            sale_from = self.env.company.currency_id
        if not cost_from:
            cost_from = self.env.company.currency_id
        return {
            "name": _("Migrate Product Currencies"),
            "type": "ir.actions.act_window",
            "res_model": "l10n.ve.product.currency.migrate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_migrate_sale": True,
                "default_migrate_cost": False,
                "default_sale_from_currency_id": sale_from.id,
                "default_cost_from_currency_id": cost_from.id,
            },
        }
