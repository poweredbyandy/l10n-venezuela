# Copyright 2026 Anderson Armeya
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("currency_rate_index_skip_sync"):
            return res
        if {
            "invoice_line_ids",
            "line_ids",
            "currency_id",
            "invoice_date",
            "date",
            "company_id",
        } & set(vals):
            self._currency_rate_index_refresh_invoice_currency_rate()
        return res

    def _currency_rate_index_refresh_invoice_currency_rate(self):
        moves = self.filtered(
            lambda move: move.state == "draft"
            and move.is_invoice(include_receipts=True)
            and move.company_id.currency_index_id
            and move.currency_id
            and move.currency_id != move.company_currency_id
        )
        if moves:
            moves._compute_expected_currency_rate()
            moves._compute_invoice_currency_rate()
