import json

from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_igtf_currency_pos_ids_json = fields.Char(
        compute="_compute_l10n_ve_igtf_currency_pos_ids_json"
    )

    @api.depends("l10n_ve_igtf_currency_ids")
    def _compute_l10n_ve_igtf_currency_pos_ids_json(self):
        for company in self:
            company.l10n_ve_igtf_currency_pos_ids_json = json.dumps(
                company.l10n_ve_igtf_currency_ids.ids
            )

    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for name in (
            "l10n_ve_igtf_feature_active",
            "l10n_ve_igtf_percent",
            "l10n_ve_igtf_currency_pos_ids_json",
        ):
            if name not in fields_list:
                fields_list.append(name)
        return fields_list
