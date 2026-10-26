def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    env["l10n_ve.default.account"]._ensure_default_accounts_menu()
