# Part of Odoo. See LICENSE file for full copyright and licensing details.


def post_init_hook(env):
    env["account.chart.template"]._l10n_ve_payroll_configure_companies()
