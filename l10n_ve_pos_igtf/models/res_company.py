from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for name in (
            "l10n_ve_igtf_feature_active",
            "l10n_ve_igtf_percent",
            "l10n_ve_igtf_currency_ids",
        ):
            if name not in fields_list:
                fields_list.append(name)
        return fields_list
