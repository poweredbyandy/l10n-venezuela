import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if version is None:
        return
    cr.execute(
        """
        UPDATE account_move am
           SET l10n_ve_process_date = ap.l10n_ve_process_date
          FROM account_payment ap
         WHERE am.l10n_ve_process_date IS NULL
           AND ap.l10n_ve_process_date IS NOT NULL
           AND (
                am.origin_payment_id = ap.id
                OR ap.move_id = am.id
           )
        """
    )
    _logger.info(
        "l10n_ve_seniat: %s asientos de pago sincronizados con fecha de proceso",
        cr.rowcount,
    )
