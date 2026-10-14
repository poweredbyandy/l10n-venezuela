# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountPayment(models.Model):
    _inherit = "account.payment"

    closing_id = fields.Many2one(
        comodel_name="account.payment.closing",
        string="Terminal Closing",
        readonly=True,
        copy=False,
        index="btree_not_null",
        ondelete="set null",
        tracking=True,
    )

    def _check_not_in_posted_closing(self):
        posted = self.filtered(lambda pay: pay.closing_id.state == "posted")
        if posted:
            raise UserError(
                _(
                    "These payments belong to a posted terminal closing. "
                    "Reset the closing to draft first:\n%(payments)s",
                    payments="\n".join(
                        f"{pay.display_name} ({pay.closing_id.name})" for pay in posted
                    ),
                )
            )

    def action_draft(self):
        self._check_not_in_posted_closing()
        return super().action_draft()

    def action_cancel(self):
        self._check_not_in_posted_closing()
        return super().action_cancel()

    def action_remove_from_closing(self):
        if any(pay.closing_id.state != "draft" for pay in self):
            raise UserError(_("Payments can only be removed from draft closings."))
        self.closing_id = False
        return True
