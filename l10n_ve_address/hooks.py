# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)

_PREVIOUS_MODULE = "l10n_ve_seniat"
_MODULE = "l10n_ve_address"
_MODELS = ("res.country.municipality", "res.country.parish")
_TABLES = ("res_country_municipality", "res_country_parish")
_PARTNER_COLUMNS = ("municipality_id", "parish_id")
_METADATA_XMLIDS = (
    "model_res_country_municipality",
    "model_res_country_parish",
    "access_res_country_municipality",
    "access_res_country_municipality_manager",
    "access_res_country_parish",
    "access_res_country_parish_manager",
    "view_res_country_municipality_tree",
    "view_res_country_municipality_form",
    "view_res_country_parish_tree",
    "view_res_country_parish_form",
    "action_res_country_municipality",
    "action_res_country_parish",
)
_RELATION_TABLES = ("res_country_municipality_res_country_state_rel",)


def _module_id(cr, name):
    cr.execute("SELECT id FROM ir_module_module WHERE name = %s", (name,))
    row = cr.fetchone()
    return row and row[0]


def _move_xmlids(cr):
    field_xmlids = [f"field_{table}__%" for table in _TABLES] + [
        f"field_{model}__{column}"
        for model in ("res_partner", "res_users")
        for column in _PARTNER_COLUMNS
    ]
    cr.execute(
        """
        UPDATE ir_model_data AS src
           SET module = %(module)s
         WHERE src.module = %(previous)s
           AND (
                src.model = ANY(%(models)s)
                OR (
                    src.model = 'res.country.state'
                    AND src.name LIKE %(states)s
                )
                OR src.name = ANY(%(metadata)s)
                OR (
                    src.model = 'ir.model.fields'
                    AND src.name LIKE ANY(%(fields)s)
                )
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
            "models": list(_MODELS),
            "states": "res\\_country\\_state\\_%",
            "metadata": list(_METADATA_XMLIDS),
            "fields": field_xmlids,
        },
    )
    return cr.rowcount


def _move_schema_ownership(cr, previous_id, module_id):
    cr.execute(
        """
        UPDATE ir_model_relation
           SET module = %s
         WHERE module = %s
           AND name = ANY(%s)
        """,
        (module_id, previous_id, list(_RELATION_TABLES)),
    )
    relations = cr.rowcount
    cr.execute(
        """
        UPDATE ir_model_constraint AS constraint_rec
           SET module = %s
          FROM ir_model AS model_rec
         WHERE constraint_rec.model = model_rec.id
           AND constraint_rec.module = %s
           AND (
                model_rec.model = ANY(%s)
                OR constraint_rec.name = ANY(%s)
           )
        """,
        (
            module_id,
            previous_id,
            list(_MODELS),
            [f"res_partner_{column}_fkey" for column in _PARTNER_COLUMNS],
        ),
    )
    return relations, cr.rowcount


def pre_init_hook(env):
    cr = env.cr
    previous_id = _module_id(cr, _PREVIOUS_MODULE)
    module_id = _module_id(cr, _MODULE)
    if not previous_id or not module_id:
        return
    xmlids = _move_xmlids(cr)
    relations, constraints = _move_schema_ownership(cr, previous_id, module_id)
    if xmlids or relations or constraints:
        _logger.info(
            "Moved from %s to %s: %s xmlids, %s relations, %s constraints",
            _PREVIOUS_MODULE,
            _MODULE,
            xmlids,
            relations,
            constraints,
        )
