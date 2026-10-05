# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)

_MODULE = "account_currency"
_INVOICE_MOVE_TYPES = ("out_invoice", "in_invoice", "out_refund", "in_refund")
_MOVE_FIELDS = (
    "invoice_currency_rate",
    "l10n_ve_inverse_rate",
    "l10n_ve_currency_rate_outdated",
    "lines_with_rate_difference",
)
_MOVE_LINE_FIELDS = (
    "price_subtotal_currency",
    "price_unit_company_currency",
    "manually_price_subtotal_currency",
    "warning_rate_difference",
)
_SENIAT_XMLIDS = (
    "model_res_currency",
    "model_inherit__res_currency__mail_thread",
    "model_inherit__res_currency__mail_activity_mixin",
    "model_inherit__res_currency_rate__mail_thread",
    "view_currency_form_l10n_ve_chatter",
    "view_currency_rate_form_l10n_ve",
)
_PREVIOUS_MODULES = {
    "l10n_ve_seniat": {
        "names": _SENIAT_XMLIDS,
        "patterns": (
            "field\\_res\\_currency\\_\\_%",
            "field\\_res\\_currency\\_rate\\_\\_%",
        ),
    },
    "currency_account": {
        "names": (),
        "patterns": (),
    },
}


def _field_xmlids():
    move_models = ("account_move", "account_bank_statement_line")
    return [
        f"field_{model}__{field}" for model in move_models for field in _MOVE_FIELDS
    ] + [f"field_account_move_line__{field}" for field in _MOVE_LINE_FIELDS]


def _move_xmlids(cr, previous, names, patterns):
    cr.execute(
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
            "previous": previous,
            "names": list(names) + _field_xmlids(),
            "patterns": list(patterns) or [""],
        },
    )
    return cr.rowcount


def _drop_stale_currency_account_move_form(cr):
    cr.execute(
        """
        SELECT view.id
          FROM ir_ui_view AS view
          JOIN ir_model_data AS imd
            ON imd.model = 'ir.ui.view'
           AND imd.res_id = view.id
         WHERE imd.module = 'currency_account'
           AND imd.name = 'view_move_form'
           AND view.arch_db::text LIKE '%%has_rate_difrerence%%'
           AND NOT EXISTS (
                SELECT 1 FROM ir_ui_view AS child WHERE child.inherit_id = view.id
           )
        """
    )
    view_ids = [row[0] for row in cr.fetchall()]
    if not view_ids:
        return
    cr.execute(
        "DELETE FROM ir_model_data WHERE model = 'ir.ui.view' AND res_id = ANY(%s)",
        (view_ids,),
    )
    cr.execute("DELETE FROM ir_ui_view WHERE id = ANY(%s)", (view_ids,))
    _logger.info("Dropped stale currency_account move form views %s", view_ids)


def pre_init_hook(env):
    cr = env.cr
    _drop_stale_currency_account_move_form(cr)
    for previous, xmlids in _PREVIOUS_MODULES.items():
        moved = _move_xmlids(cr, previous, xmlids["names"], xmlids["patterns"])
        if moved:
            _logger.info("Moved %s xmlids from %s to %s", moved, previous, _MODULE)


def recompute_price_subtotal_currency(env):
    env.cr.execute(
        """
        UPDATE account_move_line AS aml
           SET price_subtotal_currency = 0.0
          FROM account_move AS am
         WHERE am.id = aml.move_id
           AND COALESCE(aml.price_subtotal_currency, 0.0) != 0.0
           AND (
                am.move_type NOT IN %(move_types)s
                OR aml.display_type IS DISTINCT FROM 'product'
           )
        """,
        {"move_types": _INVOICE_MOVE_TYPES},
    )
    env["account.move.line"].invalidate_model(["price_subtotal_currency"])
    lines = env["account.move.line"].search(
        [
            ("move_id.move_type", "in", _INVOICE_MOVE_TYPES),
            ("display_type", "=", "product"),
            ("manually_price_subtotal_currency", "=", False),
        ]
    )
    env.add_to_compute(lines._fields["price_subtotal_currency"], lines)
    lines.flush_recordset(["price_subtotal_currency"])
    _logger.info("Recomputed price_subtotal_currency on %s lines", len(lines))


def post_init_hook(env):
    recompute_price_subtotal_currency(env)
