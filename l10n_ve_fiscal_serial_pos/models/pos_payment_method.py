# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    l10n_ve_fiscal_payment_code = fields.Char(
        related="journal_id.l10n_ve_fiscal_payment_code",
        string="Fiscal payment code",
        readonly=True,
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        for field_name in ("journal_id", "l10n_ve_fiscal_payment_code", "is_cash_count"):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list
