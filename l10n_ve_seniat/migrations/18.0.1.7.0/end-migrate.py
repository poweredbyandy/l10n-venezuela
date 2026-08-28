# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _mark_uninstalled_to_install(env, module_name):
    module = env["ir.module.module"].search([("name", "=", module_name)], limit=1)
    if not module:
        _logger.error(
            "Module %s not found in ir_module_module; run update apps list.",
            module_name,
        )
        return env["ir.module.module"]
    if module.state == "installed":
        return module
    if module.state == "uninstalled":
        module._state_update("to install", ["uninstalled"])
        _logger.info("Marked module %s as 'to install'", module_name)
    return module


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["ir.module.module"].update_list()
    loyalty = _mark_uninstalled_to_install(env, "loyalty")
    ve_loyalty = _mark_uninstalled_to_install(env, "l10n_ve_loyalty")
    if ve_loyalty.state == "installed" and "l10n.ve.discount.reason" in env:
        reasons = env["l10n.ve.discount.reason"].search_count([])
        _logger.info(
            "l10n_ve_loyalty installed after upgrade: %s discount reasons",
            reasons,
        )
        return
    _logger.info(
        "l10n_ve_loyalty end-migrate state=%s (loyalty=%s)",
        ve_loyalty.state if ve_loyalty else None,
        loyalty.state if loyalty else None,
    )
