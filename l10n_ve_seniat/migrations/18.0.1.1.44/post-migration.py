import logging

from odoo.tools import SQL
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def _process_date_column(cr, table):
    for column in ("l10n_ve_process_date", "l10n_ve_process_date_backup"):
        if column_exists(cr, table, column):
            return column
    return None


def migrate(cr, version):
    if version is None:
        return
    move_column = _process_date_column(cr, "account_move")
    payment_column = _process_date_column(cr, "account_payment")
    if not move_column or not payment_column:
        return
    cr.execute(
        SQL(
            """
            UPDATE account_move am
               SET %(move_column)s = ap.%(payment_column)s
              FROM account_payment ap
             WHERE am.%(move_column)s IS NULL
               AND ap.%(payment_column)s IS NOT NULL
               AND (
                    am.origin_payment_id = ap.id
                    OR ap.move_id = am.id
               )
            """,
            move_column=SQL.identifier(move_column),
            payment_column=SQL.identifier(payment_column),
        )
    )
    _logger.info(
        "l10n_ve_seniat: %s asientos de pago sincronizados con fecha de proceso",
        cr.rowcount,
    )
