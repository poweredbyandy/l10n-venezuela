# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import Command

_logger = logging.getLogger(__name__)

_PREVIOUS_MODULE = "l10n_ve_seniat"
_MODULE = "l10n_ve_seniat_user"
_PARTNER_XMLID = "partner_seniat"
_USER_XMLID = "user_seniat"
_LOGIN = "seniat"
_PARTNER_FIELDS = ("name", "vat", "email", "image_1920")
_SNAPSHOTS = {}


def _move_xmlids(cr):
    cr.execute(
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
        (_MODULE, _PREVIOUS_MODULE, [_PARTNER_XMLID, _USER_XMLID], _MODULE),
    )
    return [row[0] for row in cr.fetchall()]


def _xmlid(name):
    return f"{_MODULE}.{name}"


def _existing_user(env):
    user = env.ref(_xmlid(_USER_XMLID), raise_if_not_found=False)
    if user:
        return user
    user = (
        env["res.users"]
        .with_context(active_test=False)
        .search([("login", "=", _LOGIN)], limit=1)
    )
    if user:
        env["ir.model.data"]._update_xmlids(
            [{"xml_id": _xmlid(_USER_XMLID), "record": user, "noupdate": True}]
        )
        _logger.info("Adopted existing user %s as SENIAT user", _LOGIN)
    return user


def _ensure_partner_xmlid(env, user):
    if env.ref(_xmlid(_PARTNER_XMLID), raise_if_not_found=False):
        return
    env["ir.model.data"]._update_xmlids(
        [
            {
                "xml_id": _xmlid(_PARTNER_XMLID),
                "record": user.partner_id,
                "noupdate": True,
            }
        ]
    )


def pre_init_hook(env):
    moved = _move_xmlids(env.cr)
    if moved:
        _logger.info(
            "Moved from %s to %s: %s", _PREVIOUS_MODULE, _MODULE, ", ".join(moved)
        )
    user = _existing_user(env)
    if not user:
        return
    _ensure_partner_xmlid(env, user)
    partner = env.ref(_xmlid(_PARTNER_XMLID))
    _SNAPSHOTS[env.cr.dbname] = {
        "active": user.active,
        "groups": user.groups_id.ids,
        "partner": partner.read(_PARTNER_FIELDS)[0],
    }


def post_init_hook(env):
    snapshot = _SNAPSHOTS.pop(env.cr.dbname, None)
    if not snapshot:
        return
    user = env.ref(_xmlid(_USER_XMLID)).with_context(active_test=False)
    user.write(
        {
            "active": snapshot["active"],
            "groups_id": [Command.set(snapshot["groups"])],
        }
    )
    partner_values = {field: snapshot["partner"][field] for field in _PARTNER_FIELDS}
    env.ref(_xmlid(_PARTNER_XMLID)).write(partner_values)
    _logger.info("Kept the existing configuration of the SENIAT user")
