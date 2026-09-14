from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'product_template'
           AND column_name = 'force_cost_currency_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE product_template
           SET force_cost_currency_id = force_currency_id
         WHERE force_cost_currency_id IS NULL
           AND force_currency_id IS NOT NULL
        """
    )
    env = api.Environment(cr, SUPERUSER_ID, {})
    icp = env["ir.config_parameter"].sudo()
    if icp.get_param("l10n_ve_product_currency.default_force_cost_currency_id"):
        return
    sale_default = icp.get_param(
        "l10n_ve_product_currency.default_force_currency_id"
    )
    if sale_default:
        icp.set_param(
            "l10n_ve_product_currency.default_force_cost_currency_id",
            sale_default,
        )
