from email.utils import formataddr

from odoo import api, models


class ResCompany(models.Model):
    _inherit = "res.company"

    @api.model
    def l10n_ve_get_implementer_data(self):
        icp = self.env["ir.config_parameter"].sudo()
        return {
            "name": (icp.get_param("l10n_ve_seniat.implementer_name") or "").strip(),
            "vat": (icp.get_param("l10n_ve_seniat.implementer_vat") or "").strip(),
            "email": (icp.get_param("l10n_ve_seniat.implementer_email") or "").strip(),
        }

    def l10n_ve_implementer_name(self):
        return self.l10n_ve_get_implementer_data()["name"]

    def l10n_ve_implementer_vat(self):
        return self.l10n_ve_get_implementer_data()["vat"]

    def l10n_ve_implementer_email(self):
        return self.l10n_ve_get_implementer_data()["email"]

    def l10n_ve_implementer_email_from(self):
        data = self.l10n_ve_get_implementer_data()
        if data["email"] and data["name"]:
            return formataddr((data["name"], data["email"]))
        return data["email"] or False

    def l10n_ve_implementer_is_configured(self):
        data = self.l10n_ve_get_implementer_data()
        return bool(data["name"] and data["email"])
