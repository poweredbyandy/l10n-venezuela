import logging

_logger = logging.getLogger(__name__)

_OBSOLETE_VIEWS = (
    ("l10n_ve_edi", "view_picking_form_l10n_ve_edi"),
    ("l10n_ve_edi_tfhka", "sale_order_portal_content_l10n_ve_edi_tfhka_dispatch"),
)

_INSTALL_WHEN = {
    "l10n_ve_edi_stock": ("l10n_ve_stock",),
    "l10n_ve_edi_stock_tfhka": ("l10n_ve_edi_tfhka", "l10n_ve_stock"),
    "l10n_ve_edi_stock_queue_job": ("l10n_ve_edi_queue_job", "l10n_ve_stock"),
}


def _drop_obsolete_views(cr):
    for module, name in _OBSOLETE_VIEWS:
        cr.execute(
            """
            DELETE FROM ir_ui_view
             WHERE id IN (
                SELECT res_id
                  FROM ir_model_data
                 WHERE module = %s
                   AND name = %s
                   AND model = 'ir.ui.view'
             )
            """,
            (module, name),
        )
        cr.execute(
            """
            DELETE FROM ir_model_data
             WHERE module = %s
               AND name = %s
               AND model = 'ir.ui.view'
            """,
            (module, name),
        )
        if cr.rowcount:
            _logger.info("Removed obsolete view %s.%s", module, name)


def _mark_to_install(cr):
    for name, required in _INSTALL_WHEN.items():
        cr.execute(
            """
            UPDATE ir_module_module
               SET state = 'to install'
             WHERE name = %s
               AND state = 'uninstalled'
               AND (
                    SELECT count(*)
                      FROM ir_module_module
                     WHERE name = ANY(%s)
                       AND state IN ('installed', 'to upgrade', 'to install')
               ) = %s
            """,
            (name, list(required), len(required)),
        )
        if cr.rowcount:
            _logger.info("Marked %s to install", name)


def migrate(cr, version):
    if not version:
        return
    _drop_obsolete_views(cr)
    _mark_to_install(cr)
