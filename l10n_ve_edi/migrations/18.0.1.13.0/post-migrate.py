import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_DASHBOARD_MODULE = "l10n_ve_journal_dashboard_edi"


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    module = env["ir.module.module"].search(
        [("name", "=", _DASHBOARD_MODULE), ("state", "=", "uninstalled")]
    )
    if module:
        module.button_install()
        _logger.info("Marked %s to install", _DASHBOARD_MODULE)
