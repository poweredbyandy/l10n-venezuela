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
# deprecated type_person_id. When the new archs (which no longer add it)
# are validated against each other's old stored archs, the upgrade fails
# with "no puede ubicarse en la vista principal".
#
# Strategy: PATCH, don't delete. Stripping the references from the stored
# archs (self-closing <field>/<xpath> elements, on every translation) is
# enough for the XML reload to validate and rewrite the arch afterwards.
# Deleting the views breaks with a foreign key violation when another
# module's view (e.g. a customer customization such as
# jr_partner_registration) inherits them — and deleting customer views
# would silently destroy their customizations.
_LEGACY_PARTNER_VIEW_MODULES = ("l10n_ve_withholding", "l10n_ve_seniat")
# Self-closing elements referencing the field, e.g.
# <field name="type_person_id" .../>
# <xpath expr="//div[...]/field[@name='type_person_id']" position="move"/>
_LEGACY_ELEMENT_RE = r"<(field|xpath)[^>]*type_person_id[^>]*/>"


def _neutralize_legacy_partner_views(cr):
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
        return (0, 0, [])

    cr.execute(
        """
        UPDATE ir_ui_view v
           SET arch_db = (
                SELECT COALESCE(jsonb_object_agg(t.key,
                           to_jsonb(regexp_replace(t.value, %s, '', 'g'))),
                               '{}'::jsonb)
                  FROM jsonb_each_text(v.arch_db) t
               )
         WHERE v.id = ANY(%s)
        """,
        [_LEGACY_ELEMENT_RE, ids],
    )
    patched = cr.rowcount

    # Whatever could not be patched (non self-closing references) and has
    # no children: safe to delete. With children, keep it and warn — the
    # customer customized that view and the XML reload will surface the
    # remaining conflict explicitly.
    cr.execute(
        """
        SELECT v.id
          FROM ir_ui_view v
         WHERE v.id = ANY(%s)
           AND v.arch_db::text LIKE '%%type_person_id%%'
           AND NOT EXISTS (SELECT 1 FROM ir_ui_view c WHERE c.inherit_id = v.id)
        """,
        [ids],
    )
    deletable = [row[0] for row in cr.fetchall()]
    cr.execute(
        """
        SELECT v.id
          FROM ir_ui_view v
         WHERE v.id = ANY(%s)
           AND v.arch_db::text LIKE '%%type_person_id%%'
        """,
        [ids],
    )
    still_referencing = [row[0] for row in cr.fetchall()]
    for row_id in deletable:
        cr.execute(
            "DELETE FROM ir_ui_view_custom WHERE ref_id = %s", [row_id]
        )
        cr.execute(
            "DELETE FROM ir_model_data "
            "WHERE model = 'ir.ui.view' AND res_id = %s",
            [row_id],
        )
        cr.execute("DELETE FROM ir_ui_view WHERE id = %s", [row_id])
    return (patched, len(deletable), still_referencing)


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

    patched_views, dropped_views, still_referencing = (
        _neutralize_legacy_partner_views(cr)
    )
    if patched_views or dropped_views:
        _logger.info(
            "l10n_ve_withholding pre-migrate: %s vistas legadas del "
            "formulario parcheadas (sin type_person_id) y %s eliminadas; "
            "vistas sin resolver=%s",
            patched_views,
            dropped_views,
            still_referencing,
        )
        if still_referencing:
            _logger.warning(
                "l10n_ve_withholding pre-migrate: las vistas %s siguen "
                "referenciando type_person_id (elementos no "
                "self-closing y/o con vistas hijas del cliente). El reload "
                "del XML dará el detalle si algo no valida.",
                still_referencing,
            )

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
