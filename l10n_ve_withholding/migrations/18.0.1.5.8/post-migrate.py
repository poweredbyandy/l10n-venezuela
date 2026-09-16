from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env["account.retention.line"].search(
        [("payment_concept_id", "!=", False)]
    )
    lines._compute_code()
