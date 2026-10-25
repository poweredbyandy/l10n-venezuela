# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    from odoo.addons.l10n_ve_payroll.hooks import (
        _l10n_ve_ensure_calendar_paid_rest_days,
        _l10n_ve_share_payroll_master_data,
    )

    _l10n_ve_ensure_calendar_paid_rest_days(env)
    _l10n_ve_share_payroll_master_data(env)
