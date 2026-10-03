import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_EXTRACTED_MODULES = ("l10n_ve_web_version", "l10n_ve_journal_dashboard")


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    modules = env["ir.module.module"].search(
        [("name", "in", _EXTRACTED_MODULES), ("state", "=", "uninstalled")]
    )
    if modules:
        modules.button_install()
        _logger.info("Marked %s to install", ", ".join(modules.mapped("name")))
