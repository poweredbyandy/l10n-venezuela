import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

_OBSOLETE_XMLIDS = (
    "l10n_ve_edi.view_picking_form_l10n_ve_edi",
    "l10n_ve_edi_tfhka.sale_order_portal_content_l10n_ve_edi_tfhka_dispatch",
)

# name -> dependency modules that must already be present
_INSTALL_WHEN = {
    "l10n_ve_edi_stock": ("l10n_ve_stock",),
    "l10n_ve_edi_stock_tfhka": ("l10n_ve_edi_tfhka", "l10n_ve_stock"),
    "l10n_ve_edi_stock_queue_job": ("l10n_ve_edi_queue_job", "l10n_ve_stock"),
}
_READY_STATES = ("installed", "to upgrade", "to install")


def _drop_obsolete_views(env):
    for xmlid in _OBSOLETE_XMLIDS:
        record = env.ref(xmlid, raise_if_not_found=False)
        if not record:
            continue
        record.unlink()
        _logger.info("Removed obsolete view %s", xmlid)


def _mark_to_install(env):
    module_model = env["ir.module.module"]
    for name, required in _INSTALL_WHEN.items():
        required_modules = module_model.search([("name", "in", list(required))])
        if len(required_modules) != len(required):
            continue
        if any(module.state not in _READY_STATES for module in required_modules):
            continue
        module = module_model.search(
            [("name", "=", name), ("state", "=", "uninstalled")], limit=1
        )
        if not module:
            continue
        module.button_install()
        _logger.info("Marked %s to install", name)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _drop_obsolete_views(env)
    _mark_to_install(env)
