# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Snapshot every retention line before the person classification changes.

The snapshot table stays in the database as a permanent backup of what was
declared before 18.0.1.8.0 reclassified contacts (docs/adr/0002). It is not
dropped by any later migration: remove it manually once audited.
"""

import logging

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_ve_retention_line_bak_18_0_1_8_0"

# Module-owned partner-form views whose stored (old) archs reference the
# deprecated type_person_id. The old code moved that field out of the
# base_vat VIES container with sibling "move" views; when the new archs
# (which no longer add it) are validated against each other's old stored
# archs, the upgrade fails with "no puede ubicarse en la vista principal".
# Deleting both the views and their ir_model_data lets the module recreate
# them cleanly from the new XML right after.
_LEGACY_PARTNER_VIEW_MODULES = ("l10n_ve_withholding", "l10n_ve_seniat")


def _drop_legacy_partner_views(cr):
    cr.execute(
        """
        SELECT DISTINCT v.id
          FROM ir_ui_view v
          JOIN ir_model_data d
            ON d.res_id = v.id AND d.model = 'ir.ui.view'
         WHERE v.model = 'res.partner'
           AND d.module IN %s
           AND v.arch_db::text LIKE '%%type_person_id%%'
        """,
        [_LEGACY_PARTNER_VIEW_MODULES],
    )
    ids = [row[0] for row in cr.fetchall()]
    if not ids:
        return 0
    cr.execute(
        "DELETE FROM ir_ui_view_custom WHERE ref_id = ANY(%s)",
        [ids],
    )
    cr.execute(
        "DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = ANY(%s)",
        [ids],
    )
    cr.execute("DELETE FROM ir_ui_view WHERE id = ANY(%s)", [ids])
    return len(ids)


def _table_exists(cr, table):
    cr.execute(
        "SELECT EXISTS (SELECT FROM information_schema.tables "
        "WHERE table_name = %s)",
        [table],
    )
    return bool(cr.fetchone()[0])


def migrate(cr, version):
    if not _table_exists(cr, "account_retention_line"):
        return

    dropped_views = _drop_legacy_partner_views(cr)

    if _table_exists(cr, BACKUP_TABLE):
        _logger.info(
            "l10n_ve_withholding pre-migrate: el respaldo %s ya existe, no se "
            "vuelve a crear",
            BACKUP_TABLE,
        )
    else:
        cr.execute(
            f"""
            CREATE TABLE {BACKUP_TABLE} AS
            SELECT line.id,
                   line.code,
                   line.retention_amount,
                   retention.state AS retention_state,
                   now() AS snapshot_at
              FROM account_retention_line line
              LEFT JOIN account_retention retention
                     ON retention.id = line.retention_id
            """
        )
        cr.execute(f"CREATE INDEX ON {BACKUP_TABLE} (id)")
        cr.execute(f"SELECT count(*) FROM {BACKUP_TABLE}")
        snapshot = cr.fetchone()[0]
        _logger.info(
            "l10n_ve_withholding pre-migrate: respaldo de %s líneas de "
            "retención en %s",
            snapshot,
            BACKUP_TABLE,
        )

    if dropped_views:
        _logger.info(
            "l10n_ve_withholding pre-migrate: eliminadas %s vistas legadas "
            "del formulario de contacto (se recrean desde el XML nuevo)",
            dropped_views,
        )
