# Copyright 2026 Anderson Armeya
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ResCurrencyRate(models.Model):
    _inherit = "res.currency.rate"

    rate_index_synced = fields.Boolean(
        string="Synced from Index Rate",
        default=False,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        rates = super().create(vals_list)
        rates._currency_rate_index_resync_from_index_currency()
        return rates

    def write(self, vals):
        res = super().write(vals)
        if {
            "rate",
            "company_rate",
            "inverse_company_rate",
            "name",
            "currency_id",
            "company_id",
        } & set(vals):
            self._currency_rate_index_resync_from_index_currency()
        return res

    def _currency_rate_index_resync_from_index_currency(self):
        if self.env.context.get("currency_rate_index_skip_sync"):
            return
        IndexRate = self.env["res.currency.rate.index"]
        to_sync = IndexRate.browse()
        for rate in self:
            company = rate.company_id or self.env.company.root_id
            if rate.currency_id != company.currency_index_id:
                continue
            to_sync |= IndexRate.search(
                [
                    ("name", "=", rate.name),
                    ("company_id", "in", (False, company.id)),
                ]
            )
        if to_sync:
            to_sync._sync_native_rate_from_index()
