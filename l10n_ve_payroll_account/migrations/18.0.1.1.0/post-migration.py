# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    env["account.chart.template"]._l10n_ve_payroll_configure_companies()
