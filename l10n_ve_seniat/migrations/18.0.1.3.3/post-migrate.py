import logging

_logger = logging.getLogger(__name__)


def _table_exists(cr, table_name):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.tables
         WHERE table_name = %s
        """,
        (table_name,),
    )
    return bool(cr.fetchone())


def _column_exists(cr, table_name, column_name):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = %s
           AND column_name = %s
        """,
        (table_name, column_name),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return
    if not _table_exists(cr, "l10n_ve_discount_reason"):
        return
    if not _table_exists(cr, "l10n_ve_account_move_discount"):
        return
    if not _column_exists(cr, "l10n_ve_account_move_discount", "reason_id"):
        return

    cr.execute(
        """
        SELECT id, name
          FROM l10n_ve_discount_reason
         WHERE COALESCE(active, TRUE) IS TRUE
         ORDER BY sequence, id
         LIMIT 1
        """
    )
    row = cr.fetchone()
    if not row:
        return

    reason_id, reason_name = row
    if _column_exists(cr, "l10n_ve_account_move_discount", "name"):
        cr.execute(
            """
            UPDATE l10n_ve_account_move_discount
               SET reason_id = %s,
                   name = %s
             WHERE reason_id IS NULL
            """,
            (reason_id, reason_name),
        )
    else:
        cr.execute(
            """
            UPDATE l10n_ve_account_move_discount
               SET reason_id = %s
             WHERE reason_id IS NULL
            """,
            (reason_id,),
        )
    if cr.rowcount:
        _logger.info(
            "Assigned default discount reason to %s account move discount records",
            cr.rowcount,
        )
