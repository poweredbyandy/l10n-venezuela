from odoo import SUPERUSER_ID, api

_OBSOLETE_VIEWS = {
    "l10n_ve_seniat.res_company_form_view_seniat": "l10n_ve_base.view_company_form",
}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, replacement_xmlid in _OBSOLETE_VIEWS.items():
        view = env.ref(xmlid, raise_if_not_found=False)
        if not view:
            continue
        replacement = env.ref(replacement_xmlid, raise_if_not_found=False)
        if replacement:
            cr.execute(
                "UPDATE ir_ui_view SET inherit_id = %s WHERE inherit_id = %s",
                (replacement.id, view.id),
            )
        else:
            env["ir.ui.view"].with_context(active_test=False).search(
                [("inherit_id", "=", view.id)]
            ).unlink()
        view.unlink()
