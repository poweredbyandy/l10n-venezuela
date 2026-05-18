from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_retention = fields.Boolean(
        string="Is retention",
        help="Check this box if this payment is a retention",
        copy=False,
    )
    l10n_ve_process_date = fields.Date(
        string="Fecha de proceso",
        copy=False,
        tracking=True,
    )

    def _l10n_ve_set_process_date_on_validation(self):
        today = fields.Date.context_today(self)
        for payment in self.filtered(lambda pay: pay.state in ("in_process", "paid")):
            process_date = payment.l10n_ve_process_date or today
            if not payment.l10n_ve_process_date:
                payment.l10n_ve_process_date = process_date
            if payment.move_id and not payment.move_id.l10n_ve_process_date:
                payment.move_id.l10n_ve_process_date = process_date

    def write(self, vals):
        res = super().write(vals)
        if "state" in vals:
            self._l10n_ve_set_process_date_on_validation()
        return res

    def action_draft(self):
        res = super().action_draft()
        self.write({"l10n_ve_process_date": False})
        return res
