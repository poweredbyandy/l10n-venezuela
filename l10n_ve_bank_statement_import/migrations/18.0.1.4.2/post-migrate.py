from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    mapping = env.ref(
        "l10n_ve_bank_statement_import.banco_bnc_txt_statement_map",
        raise_if_not_found=False,
    )
    if not mapping or mapping.timestamp_column != "Fecha":
        return
    mapping.write(
        {
            "timestamp_column": "Fecha,Hora",
            "timestamp_format": "%d/%m/%Y %H:%M:%S.%f",
            "amount_debit_column": "Haber",
            "amount_credit_column": "Debe",
            "amount_inverse_sign": False,
        }
    )
