# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)

_VIEW_XMLIDS = ("login_version_label",)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT res_id
          FROM ir_model_data
         WHERE module = 'l10n_ve_seniat'
           AND model = 'ir.ui.view'
           AND name = ANY(%s)
        """,
        (list(_VIEW_XMLIDS),),
    )
    view_ids = [row[0] for row in cr.fetchall() if row[0]]
    if not view_ids:
        return
    cr.execute("DELETE FROM ir_ui_view WHERE id = ANY(%s)", (view_ids,))
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'l10n_ve_seniat'
           AND model = 'ir.ui.view'
           AND name = ANY(%s)
        """,
        (list(_VIEW_XMLIDS),),
    )
    _logger.info(
        "Removed login version view from l10n_ve_seniat: %s",
        ", ".join(_VIEW_XMLIDS),
    )
