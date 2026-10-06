from odoo.addons.account_currency.hooks import drop_stale_currency_account_move_form


def migrate(cr, version):
    drop_stale_currency_account_move_form(cr)
