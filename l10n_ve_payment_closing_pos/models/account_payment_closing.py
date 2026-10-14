# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountPaymentClosing(models.Model):
    _inherit = "account.payment.closing"

    pos_payment_method_ids = fields.Many2many(
        comodel_name="pos.payment.method",
        string="POS Payment Methods",
        domain="[('journal_id', '=', journal_id)]",
        help="Point of Sale payment methods (terminals) included in the closing.",
    )

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        res = super()._onchange_journal_id()
        self.pos_payment_method_ids = False
        return res

    def _get_payment_method_domains(self):
        domains = super()._get_payment_method_domains()
        if self.pos_payment_method_ids:
            domains.append(
                [("pos_payment_method_id", "in", self.pos_payment_method_ids.ids)]
            )
        return domains
