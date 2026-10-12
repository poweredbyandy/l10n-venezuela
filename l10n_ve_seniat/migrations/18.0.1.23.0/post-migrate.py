import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_TEMPLATES = ("ve_seniat", "ve_seniat_basic", "ve_seniat_empty")
_MODULE = "l10n_ve_coa"


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        "SELECT 1 FROM res_company WHERE chart_template IN %s LIMIT 1",
        (_TEMPLATES,),
    )
    if not cr.fetchone():
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Module = env["ir.module.module"]
    module = Module.search([("name", "=", _MODULE)], limit=1)
    if not module:
        Module.update_list()
        module = Module.search([("name", "=", _MODULE)], limit=1)
    if not module:
        _logger.error("Module %s not found; chart templates are unavailable", _MODULE)
        return
    if module.state == "uninstalled":
        module.button_install()
        _logger.info("Marked %s to install", _MODULE)
