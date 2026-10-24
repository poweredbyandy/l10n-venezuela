# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'res_company_l10n_ve_emission_medium_rel'
        """
    )
    if cr.fetchone():
        cr.execute("DROP TABLE IF EXISTS res_company_l10n_ve_emission_medium_rel")
        _logger.info("Dropped res_company_l10n_ve_emission_medium_rel")

    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE module = 'l10n_ve_seniat'
          AND model = 'l10n.ve.emission.medium'
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_access
        WHERE model_id IN (
            SELECT id FROM ir_model WHERE model = 'l10n.ve.emission.medium'
        )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_fields
        WHERE model = 'l10n.ve.emission.medium'
           OR (
                model = 'res.company'
                AND name IN (
                    'l10n_ve_emission_medium_ids',
                    'l10n_ve_has_free_form',
                    'l10n_ve_has_fiscal_machine',
                    'l10n_ve_has_digital_billing'
                )
           )
           OR (
                model = 'res.config.settings'
                AND name = 'l10n_ve_emission_medium_ids'
           )
        """
    )
    cr.execute("DELETE FROM ir_model WHERE model = 'l10n.ve.emission.medium'")

    cr.execute(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = 'l10n_ve_emission_medium'
        """
    )
    if cr.fetchone():
        cr.execute("DROP TABLE IF EXISTS l10n_ve_emission_medium CASCADE")
        _logger.info("Dropped l10n_ve_emission_medium")
