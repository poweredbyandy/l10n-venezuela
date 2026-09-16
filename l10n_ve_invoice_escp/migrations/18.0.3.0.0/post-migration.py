from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    report = env.ref(
        "l10n_ve_invoice_escp.l10n_ve_escp_report_invoice", raise_if_not_found=False
    )
    if not report:
        return
    journals = env["account.journal"].with_context(active_test=False)
    domain = [
        ("type", "=", "sale"),
        ("l10n_ve_free_form_print_medium", "=", "continuous"),
        ("l10n_ve_escp_report_id", "=", False),
    ]
    journals.search(domain).write({"l10n_ve_escp_report_id": report.id})
    if column_exists(cr, "account_journal", "l10n_ve_escp_layout_id"):
        cr.execute(
            """
            UPDATE account_journal
               SET l10n_ve_escp_report_id = %s
             WHERE l10n_ve_escp_layout_id IS NOT NULL
               AND l10n_ve_escp_report_id IS NULL
            """,
            (report.id,),
        )
