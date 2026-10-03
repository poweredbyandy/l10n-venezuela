import logging

_logger = logging.getLogger(__name__)

_DASHBOARD_MODULE = "l10n_ve_journal_dashboard_stock"
_XMLIDS = (
    "stock_picking_unfactured_dispatch_guide_tree",
    "stock_picking_unfactured_dispatch_guide_search",
    "action_l10n_ve_unfactured_dispatch_guides",
)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE ir_model_data AS src
           SET module = %s
         WHERE src.module = 'l10n_ve_stock'
           AND src.name = ANY(%s)
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data AS dst
                 WHERE dst.module = %s
                   AND dst.name = src.name
           )
        RETURNING src.name
        """,
        (_DASHBOARD_MODULE, list(_XMLIDS), _DASHBOARD_MODULE),
    )
    moved = [row[0] for row in cr.fetchall()]
    if moved:
        _logger.info(
            "Moved dashboard records from l10n_ve_stock to %s: %s",
            _DASHBOARD_MODULE,
            ", ".join(moved),
        )
