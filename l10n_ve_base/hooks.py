import logging

_logger = logging.getLogger(__name__)

_MODULE = "l10n_ve_base"
_PREVIOUS_MODULE = "l10n_ve_seniat"
_MOVE_FIELDS = (
    "l10n_ve_invoice_date",
    "l10n_ve_control_number",
    "l10n_ve_serial_number",
    "l10n_ve_invoice_number",
    "l10n_ve_report_z",
    "l10n_ve_on_behalf_of_third_party",
    "l10n_ve_third_party_partner_id",
    "l10n_ve_journal_emission_medium",
)
_XMLIDS = (
    "field_account_journal__l10n_ve_emission_medium",
    "field_account_tax_group__l10n_ve_aliquot_type",
    "field_res_partner__taxpayer_type",
    "field_res_users__taxpayer_type",
    "field_res_company__taxpayer_type",
)
_PATTERNS = (
    "selection\\_\\_account\\_journal\\_\\_l10n\\_ve\\_emission\\_medium\\_\\_%",
    "selection\\_\\_account\\_tax\\_group\\_\\_l10n\\_ve\\_aliquot\\_type\\_\\_%",
    "selection\\_\\_res\\_partner\\_\\_taxpayer\\_type\\_\\_%",
)


def _xmlids():
    move_models = ("account_move", "account_bank_statement_line")
    return [
        f"field_{model}__{field}" for model in move_models for field in _MOVE_FIELDS
    ] + list(_XMLIDS)


def pre_init_hook(env):
    env.cr.execute(
        """
        UPDATE ir_model_data AS src
           SET module = %(module)s
         WHERE src.module = %(previous)s
           AND (
                src.name = ANY(%(names)s)
                OR src.name LIKE ANY(%(patterns)s)
           )
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data AS dst
                 WHERE dst.module = %(module)s
                   AND dst.name = src.name
           )
        """,
        {
            "module": _MODULE,
            "previous": _PREVIOUS_MODULE,
            "names": _xmlids(),
            "patterns": list(_PATTERNS),
        },
    )
    if env.cr.rowcount:
        _logger.info(
            "Moved %s xmlids from %s to %s", env.cr.rowcount, _PREVIOUS_MODULE, _MODULE
        )
