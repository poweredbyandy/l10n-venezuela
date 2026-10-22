from odoo import SUPERUSER_ID, api

from odoo.addons.account_currency.hooks import recompute_price_subtotal_currency


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    recompute_price_subtotal_currency(env)
