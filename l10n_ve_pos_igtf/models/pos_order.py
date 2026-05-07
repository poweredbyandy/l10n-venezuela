from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    igtf_amount = fields.Float(string="IGTF")
    bi_igtf = fields.Float(string="Base IGTF")

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = list(super()._load_pos_data_fields(config_id))
        for name in ("igtf_amount", "bi_igtf"):
            if name not in fields_list:
                fields_list.append(name)
        return fields_list
