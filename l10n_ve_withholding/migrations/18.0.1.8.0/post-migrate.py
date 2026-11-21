# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Backfill the new concept-line classification and freeze declared history.

Steps (docs/adr/0001 and docs/adr/0002):

1. ``payment.concept.line``: translate the frozen ``type_person_id`` into
   ``(l10n_ve_person_type, l10n_ve_islr_category)`` through
   ``TYPE_PERSON_MAP`` (by xml_id, never by name). The seeded CSV rows are
   rewritten by Odoo during the upgrade; this covers custom/edited lines.
2. ``res.partner``: default ``l10n_ve_islr_category`` to ``standard`` and
   translate the frozen ``type_person_id`` of the special categories
   (financial institution, other PJ, radio broadcaster).
3. Restore the frozen ``code``/``retention_amount`` of emitted/cancelled
   retention lines from the pre-migrate snapshot, as a belt-and-suspenders
   guard on top of the compute freeze.

Lines that cannot be mapped (custom ``type.person`` records) keep the new
columns NULL, are reported in the log, and still match through the legacy
fallback in ``_l10n_ve_get_payment_concept_line``.
"""

import logging

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_ve_retention_line_bak_18_0_1_8_0"


def _table_exists(cr, table):
    cr.execute(
        "SELECT EXISTS (SELECT FROM information_schema.tables "
        "WHERE table_name = %s)",
        [table],
    )
    return bool(cr.fetchone()[0])


def _backfill_concept_lines(cr):
    """Translate type_person_id -> (person_type, islr_category) by xml_id."""
    from odoo.addons.l10n_ve_withholding.models.type_person import TYPE_PERSON_MAP

    mapped = 0
    unmapped = []
    for xml_id, (person_type, category) in TYPE_PERSON_MAP.items():
        module, name = xml_id.split(".", 1)
        cr.execute("SELECT id FROM ir_model_data WHERE module=%s AND name=%s",
                   [module, name])
        row = cr.fetchone()
        if not row:
            continue
        cr.execute(
            """
            UPDATE payment_concept_line
               SET l10n_ve_person_type = %s,
                   l10n_ve_islr_category = %s
             WHERE type_person_id = %s
               AND l10n_ve_person_type IS NULL
            """,
            [person_type, category, row[0]],
        )
        mapped += cr.rowcount
    cr.execute(
        """
        SELECT count(*) FROM payment_concept_line
         WHERE l10n_ve_person_type IS NULL AND type_person_id IS NOT NULL
        """
    )
    unmapped_count = cr.fetchone()[0]
    if unmapped_count:
        cr.execute(
            """
            SELECT id, code, COALESCE(type_person_id, 0)
              FROM payment_concept_line
             WHERE l10n_ve_person_type IS NULL AND type_person_id IS NOT NULL
             LIMIT 20
            """
        )
        unmapped = cr.fetchall()
    return mapped, unmapped_count, unmapped


def _backfill_partner_category(cr):
    """Default standard category + translate the special frozen types."""
    cr.execute(
        "SELECT id FROM ir_model_data WHERE module='l10n_ve_withholding' "
        "AND name=%s",
        ["type_person_five_l10n_ve_withholding"],
    )
    financial = cr.fetchone()
    cr.execute(
        "SELECT id FROM ir_model_data WHERE module='l10n_ve_withholding' "
        "AND name=%s",
        ["type_person_six_l10n_ve_withholding"],
    )
    other = cr.fetchone()
    cr.execute(
        "SELECT id FROM ir_model_data WHERE module='l10n_ve_withholding' "
        "AND name=%s",
        ["type_person_seven_l10n_ve_withholding"],
    )
    radio = cr.fetchone()

    cr.execute(
        """
        UPDATE res_partner
           SET l10n_ve_islr_category = 'standard'
         WHERE l10n_ve_islr_category IS NULL
        """
    )
    standard = cr.rowcount

    special = 0
    for row, category in (
        (financial, "financial_institution"),
        (other, "other"),
        (radio, "radio_broadcaster"),
    ):
        if not row:
            continue
        cr.execute(
            """
            UPDATE res_partner
               SET l10n_ve_islr_category = %s
             WHERE type_person_id = %s
            """,
            [category, row[0]],
        )
        special += cr.rowcount
    return standard, special


def _restore_frozen_lines(cr):
    """Restore emitted/cancelled lines from the pre-migrate snapshot."""
    if not _table_exists(cr, BACKUP_TABLE):
        _logger.warning(
            "l10n_ve_withholding post-migrate: sin tabla de respaldo %s, no "
            "se restauran líneas congeladas",
            BACKUP_TABLE,
        )
        return 0
    cr.execute(
        f"""
        UPDATE account_retention_line line
           SET code = backup.code,
               retention_amount = backup.retention_amount
          FROM {BACKUP_TABLE} backup,
               account_retention retention
         WHERE line.id = backup.id
           AND retention.id = line.retention_id
           AND retention.state IN ('emitted', 'cancel')
           AND (line.code IS DISTINCT FROM backup.code
                OR line.retention_amount IS DISTINCT FROM
                   backup.retention_amount)
        """
    )
    return cr.rowcount


def migrate(cr, version):
    if not _table_exists(cr, "payment_concept_line"):
        return

    mapped, unmapped_count, unmapped_sample = _backfill_concept_lines(cr)
    standard, special = _backfill_partner_category(cr)
    restored = _restore_frozen_lines(cr)

    cr.execute(
        """
        SELECT l10n_ve_person_type, count(*)
          FROM payment_concept_line
         GROUP BY 1
         ORDER BY 2 DESC
        """
    )
    distribution = {key or "(sin migrar)": count for key, count in cr.fetchall()}

    _logger.info(
        "l10n_ve_withholding 18.0.1.8.0 post-migrate: líneas de concepto "
        "migradas=%s sin_mapear=%s categoría_standard=%s categoría_especial=%s "
        "líneas_congeladas_restauradas=%s distribución=%s",
        mapped,
        unmapped_count,
        standard,
        special,
        restored,
        distribution,
    )
    if unmapped_sample:
        _logger.warning(
            "l10n_ve_withholding: líneas de concepto sin clasificación nueva "
            "(siguen matcheando por type_person_id deprecado): %s",
            unmapped_sample,
        )
