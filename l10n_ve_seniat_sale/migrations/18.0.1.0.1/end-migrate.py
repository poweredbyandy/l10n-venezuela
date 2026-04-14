def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    env["ir.actions.report"]._l10n_ve_unbind_extra_sale_order_pdf_reports()
