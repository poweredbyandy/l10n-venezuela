from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if version is None:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    partner = env.ref("l10n_ve_seniat.partner_seniat", raise_if_not_found=False)
    if partner and partner.vat != "G200003030":
        partner.with_context(skip_l10n_ve_vat_rif_format_check=True).write(
            {"vat": "G200003030"}
        )
