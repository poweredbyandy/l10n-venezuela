import logging

from odoo.tools.sql import column_exists, rename_column

_logger = logging.getLogger(__name__)

_FIELD = "l10n_ve_process_date"
_BACKUP_COLUMN = "l10n_ve_process_date_backup"
_TABLES = {
    "account_move": "account.move",
    "account_payment": "account.payment",
}


def _field_owned_by_other_module(cr, model):
    cr.execute(
        """
        SELECT 1
          FROM ir_model_data imd
          JOIN ir_model_fields imf ON imf.id = imd.res_id
         WHERE imd.model = 'ir.model.fields'
           AND imd.module != 'l10n_ve_seniat'
           AND imf.model = %s
           AND imf.name = %s
         LIMIT 1
        """,
        (model, _FIELD),
    )
    return bool(cr.fetchone())


def _drop_payment_process_date_view(cr):
    cr.execute(
        """
        WITH removed AS (
            DELETE FROM ir_model_data
             WHERE module = 'l10n_ve_seniat'
               AND name = 'view_account_payment_form_l10n_ve'
         RETURNING res_id
        )
        DELETE FROM ir_ui_view
         WHERE id IN (SELECT res_id FROM removed)
        """
    )


def migrate(cr, version):
    _drop_payment_process_date_view(cr)
    for table, model in _TABLES.items():
        if not column_exists(cr, table, _FIELD):
            continue
        if column_exists(cr, table, _BACKUP_COLUMN):
            continue
        if _field_owned_by_other_module(cr, model):
            continue
        rename_column(cr, table, _FIELD, _BACKUP_COLUMN)
        _logger.info(
            "l10n_ve_seniat: %s.%s respaldada en %s hasta instalar "
            "account_process_date",
            table,
            _FIELD,
            _BACKUP_COLUMN,
        )
