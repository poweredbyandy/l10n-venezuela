from odoo import SUPERUSER_ID, api

from odoo.addons.account_currency.hooks import realign_posted_foreign_company_tax


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    realign_posted_foreign_company_tax(env)
