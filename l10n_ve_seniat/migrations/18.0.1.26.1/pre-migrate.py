# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Transition for the partner form "only editable fields" redesign.

18.0.1.26.1 removes the read-only classification fields (nature, person
type, fine residence label) from the contact form; they are now reachable
as an optional column of the contacts list. The person type stays in the
form only as a hidden field used by other fields' modifiers.

DBs upgraded through 18.0.1.26.0 hold stored view archs that move those
fields around the base_vat VIES container. When the new archs (which no
longer add them) are validated against each other's old stored archs, the
upgrade fails with "no puede ubicarse en la vista principal". Deleting the
module-owned partner views that reference the removed fields (and their
ir_model_data) lets the module recreate them cleanly from the new XML.
Fresh installs have nothing to clean up.
"""

import logging

_logger = logging.getLogger(__name__)

# Module-owned partner views whose stored archs reference removed
# read-only fields.
_REMOVED_FIELD_PATTERNS = (
    "%l10n_ve_person_nature%",
    "%l10n_ve_person_type%",
    "%l10n_ve_tax_residence_name%",
)


def _table_exists(cr, table):
    cr.execute(
        "SELECT EXISTS (SELECT FROM information_schema.tables "
        "WHERE table_name = %s)",
        [table],
    )
    return bool(cr.fetchone()[0])


def migrate(cr, version):
    if not _table_exists(cr, "ir_ui_view"):
        return

    patterns = " OR ".join(
        f"v.arch_db::text LIKE %s" for _ in _REMOVED_FIELD_PATTERNS
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
        """,
        list(_REMOVED_FIELD_PATTERNS),
    )
    ids = [row[0] for row in cr.fetchall()]
    if not ids:
        return

    cr.execute("DELETE FROM ir_ui_view_custom WHERE ref_id = ANY(%s)", [ids])
    cr.execute(
        "DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = ANY(%s)",
        [ids],
    )
    cr.execute("DELETE FROM ir_ui_view WHERE id = ANY(%s)", [ids])
    _logger.info(
        "l10n_ve_seniat 18.0.1.26.1 pre-migrate: eliminadas %s vistas legadas "
        "del formulario de contacto con campos de solo lectura (se recrean "
        "desde el XML nuevo)",
        len(ids),
    )
