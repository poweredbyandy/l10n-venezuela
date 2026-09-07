from odoo import api, models


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.depends(
        "journal_id",
        "partner_id",
        "partner_type",
        "payment_type",
        "payment_has_invoice_lines",
        "is_retention",
    )
    def _compute_destination_account_id(self):
        return super()._compute_destination_account_id()

    def _should_post_to_customer_advance_account(self):
        self.ensure_one()
        if self.is_retention:
            return False
        return super()._should_post_to_customer_advance_account()

    def _should_post_to_supplier_advance_account(self):
        self.ensure_one()
        if self.is_retention:
            return False
        return super()._should_post_to_supplier_advance_account()
