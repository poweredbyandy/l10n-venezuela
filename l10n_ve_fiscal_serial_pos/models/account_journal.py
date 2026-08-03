from odoo import api, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        if "l10n_ve_fiscal_machine_id" not in fields:
            fields.append("l10n_ve_fiscal_machine_id")
        return fields
