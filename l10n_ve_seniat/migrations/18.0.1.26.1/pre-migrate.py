# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Transition for the partner form "only editable fields" redesign.

18.0.1.26.1 removes the read-only classification fields (nature, person
type, fine residence label) from the contact form; they are now reachable
as an optional column of the contacts list. The person type stays in the
form only as a hidden field used by other fields' modifiers.

DBs upgraded through 18.0.1.26.0 hold stored view archs that reference the
removed fields; when the new archs (which no longer add them) are validated
against the old stored ones, the upgrade fails with "no puede ubicarse en
la vista principal".

Strategy: PATCH, don't delete. Stripping the references from the stored
archs (self-closing <field>/<xpath> elements, on every translation) lets
the XML reload validate and rewrite the arch afterwards. Deleting the
views instead would break with a foreign key violation whenever another
module's view (e.g. a customer customization) inherits them, and would
silently destroy that customization. Fresh installs have nothing to clean
up.
"""

import logging

_logger = logging.getLogger(__name__)

_REMOVED_FIELDS = (
    "l10n_ve_person_nature",
    "l10n_ve_person_type",
    "l10n_ve_tax_residence_name",
)


def _table_exists(cr, table):
    cr.execute(
        "SELECT EXISTS (SELECT FROM information_schema.tables "
        "WHERE table_name = %s)",
        [table],
    )
    return bool(cr.fetchone()[0])


def _neutralize_legacy_partner_views(cr):
    patterns = " OR ".join(
        f"v.arch_db::text LIKE '%%{field}%%'" for field in _REMOVED_FIELDS
    )
    element_regex = "|".join(
        rf"<(field|xpath)[^>]*{field}[^>]*/>" for field in _REMOVED_FIELDS
    )
    cr.execute(
        f"""
        SELECT DISTINCT v.id
          FROM ir_ui_view v
          JOIN ir_model_data d
            ON d.res_id = v.id AND d.model = 'ir.ui.view'
         WHERE v.model = 'res.partner'
           AND d.module = 'l10n_ve_seniat'
           AND ({patterns})
        """
    )
    ids = [row[0] for row in cr.fetchall()]
    if not ids:
        return (0, [])

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
        [element_regex, ids],
    )
    patched = cr.rowcount
    # Whatever could not be patched (non self-closing references) is kept
    # as-is: deleting could violate the inherit foreign key when customer
    # views inherit ours. The XML reload will surface the conflict
    # explicitly if one remains.
    cr.execute(
        f"""
        SELECT v.id
          FROM ir_ui_view v
         WHERE v.id = ANY(%s)
           AND ({patterns})
        """,
        [ids],
    )
    still_referencing = [row[0] for row in cr.fetchall()]
    return (patched, still_referencing)


def migrate(cr, version):
    if not _table_exists(cr, "ir_ui_view"):
        return

    patched, still_referencing = _neutralize_legacy_partner_views(cr)
    if not patched and not still_referencing:
        return
    _logger.info(
        "l10n_ve_seniat 18.0.1.26.1 pre-migrate: %s vistas legadas del "
        "formulario parcheadas (quitados los campos de solo lectura); "
        "vistas sin resolver=%s",
        patched,
        still_referencing,
    )
    if still_referencing:
        _logger.warning(
            "l10n_ve_seniat 18.0.1.26.1 pre-migrate: las vistas %s siguen "
            "referenciando los campos ocultos (elementos no self-closing "
            "y/o con vistas hijas del cliente). El reload del XML dará el "
            "detalle si algo no valida.",
            still_referencing,
        )
