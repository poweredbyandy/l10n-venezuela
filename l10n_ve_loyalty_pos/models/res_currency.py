# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    @api.model
    def _load_pos_data_domain(self, data):
        domain = super()._load_pos_data_domain(data)
        config = self.env["pos.config"].browse(data["pos.config"]["data"][0]["id"])
        program_currency_ids = (
            config._get_program_ids()
            .filtered(lambda program: program.program_type in ("ewallet", "gift_card"))
            .mapped("currency_id")
            .ids
        )
        if not program_currency_ids:
            return domain
        # currency_pos (and similar) may already load all active currencies.
        if domain and domain[0][0] == "active":
            return domain
        currency_ids = set(program_currency_ids)
        payment_currency_ids = config.payment_method_ids.mapped("payment_currency_id").ids
        currency_ids.update(payment_currency_ids)
        if config.company_id.currency_id:
            currency_ids.add(config.company_id.currency_id.id)
        if config.currency_id:
            currency_ids.add(config.currency_id.id)
        if domain and domain[0][0] == "id" and domain[0][1] == "=":
            currency_ids.add(domain[0][2])
        elif domain and domain[0][0] == "id" and domain[0][1] == "in":
            currency_ids.update(domain[0][2] or [])
        return [("id", "in", list(currency_ids))]

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if "inverse_rate" not in fields_list:
            fields_list.append("inverse_rate")
        return fields_list
