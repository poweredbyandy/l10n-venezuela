# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.l10n_ve_payroll.hooks import _l10n_ve_ensure_calendar_paid_rest_days

    _l10n_ve_ensure_calendar_paid_rest_days(env)
