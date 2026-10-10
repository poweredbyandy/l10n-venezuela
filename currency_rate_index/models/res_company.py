# Copyright 2026 Anderson Armeya
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    currency_index_id = fields.Many2one(
        "res.currency",
        string="Moneda índice",
        help=(
            "Moneda usada como índice para conversiones directas entre monedas "
            "extranjeras. Si está vacío, las conversiones usan las tasas nativas "
            "contra la moneda de la compañía."
        ),
    )

    def write(self, vals):
        res = super().write(vals)
        if vals.get("currency_index_id"):
            self.env["res.currency.rate.index"].search(
                [("company_id", "in", (False, *self.root_id.ids))]
            )._sync_native_rate_from_index()
        return res

    @api.constrains("currency_index_id", "currency_id")
    def _check_currency_index_id(self):
        for company in self:
            if (
                company.currency_index_id
                and company.currency_id
                and company.currency_index_id == company.currency_id
            ):
                raise ValidationError(
                    _(
                        "La moneda índice no puede ser la misma que la moneda "
                        "de la compañía."
                    )
                )
