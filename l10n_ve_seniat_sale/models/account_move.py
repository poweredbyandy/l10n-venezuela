# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_credit_note_line_match_sale_lines(self, line):
        return tuple(sorted(line.sale_line_ids.ids))

    def _l10n_ve_credit_note_line_match_key(self, line):
        return super()._l10n_ve_credit_note_line_match_key(line) + (
            self._l10n_ve_credit_note_line_match_sale_lines(line),
        )

    def _l10n_ve_credit_note_line_company_match_key(self, line):
        return super()._l10n_ve_credit_note_line_company_match_key(line) + (
            self._l10n_ve_credit_note_line_match_sale_lines(line),
        )

    def _l10n_ve_refund_line_product_pair_key(self, line):
        key = super()._l10n_ve_refund_line_product_pair_key(line)
        if line.display_type in ("product", "cogs"):
            return key + (self._l10n_ve_credit_note_line_match_sale_lines(line),)
        return key
