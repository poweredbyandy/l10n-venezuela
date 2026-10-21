from odoo import SUPERUSER_ID, api

from odoo.addons.l10n_ve_reports.hooks import align_posted_tax_base_to_tax_totals


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    align_posted_tax_base_to_tax_totals(env)
