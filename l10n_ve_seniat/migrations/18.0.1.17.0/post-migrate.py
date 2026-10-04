import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_MODULE = "l10n_ve_seniat_user"


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    if not env.ref("l10n_ve_seniat.user_seniat", raise_if_not_found=False):
        return
    module = env["ir.module.module"].search(
        [("name", "=", _MODULE), ("state", "=", "uninstalled")]
    )
    if module:
        module.button_install()
        _logger.info("Marked %s to install", _MODULE)
