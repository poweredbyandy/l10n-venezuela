# Part of Odoo. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    env["res.company"].search([])._l10n_ve_fiscal_ensure_payment_methods()
