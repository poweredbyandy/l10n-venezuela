# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)

_PREVIOUS_MODULE = "l10n_ve_seniat"
_MODULE = "l10n_ve_base_vat"
_FIELD_XMLIDS = (
    "field_res_company__l10n_ve_validate_partner_vat_format",
    "field_res_config_settings__l10n_ve_validate_partner_vat_format",
)


def pre_init_hook(env):
    env.cr.execute(
        """
        UPDATE ir_model_data AS src
           SET module = %s
         WHERE src.module = %s
           AND src.name = ANY(%s)
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data AS dst
                 WHERE dst.module = %s
                   AND dst.name = src.name
           )
        RETURNING src.name
        """,
        (_MODULE, _PREVIOUS_MODULE, list(_FIELD_XMLIDS), _MODULE),
    )
    moved = [row[0] for row in env.cr.fetchall()]
    if moved:
        _logger.info(
            "Moved fields from %s to %s: %s",
            _PREVIOUS_MODULE,
            _MODULE,
            ", ".join(moved),
        )
