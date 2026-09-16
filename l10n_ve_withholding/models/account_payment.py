import logging

from odoo import Command, fields, models

_logger = logging.getLogger(__name__)


class AccountPayment(models.Model):
    _inherit = "account.payment"

    is_retention = fields.Boolean(
        string="Is retention",
        help="Check this box if this payment is a retention",
        default=False,
        copy=False,
    )

    payment_type_retention = fields.Selection(
        [
            ("iva", "IVA"),
            ("islr", "ISLR"),
            ("municipal", "Municipal"),
        ],
        copy=False,
    )
    retention_id = fields.Many2one("account.retention", ondelete="cascade")

    retention_line_ids = fields.One2many(
        "account.retention.line",
        "payment_id",
        string="Retention Lines",
        store=True,
        copy=False,
    )

    invoice_line_ids = fields.Many2many(
        "account.move.line",
        domain="[('tax_ids', '!=', False)]",
        string="Invoice Lines",
        store=True,
        copy=False,
    )

    retention_ref = fields.Char(
        string="Retention reference",
        related="retention_id.number",
        store=True,
        copy=False,
    )

    def unlink(self):
        for payment in self:
            if any(isinstance(id, models.NewId) for id in self.retention_line_ids.ids):
                payment.retention_line_ids = False
            else:
                payment.retention_line_ids = [Command.clear()]
        return super().unlink()

    def compute_retention_amount_from_retention_lines(self):
        """
        Compute the amount from the retention lines.
        """
        for payment in self:
            payment.amount = sum(payment.retention_line_ids.mapped("retention_amount"))

    def _l10n_ve_get_retention_outstanding_account(self):
        self.ensure_one()
        return (
            self.payment_method_line_id.payment_account_id
            or self.journal_id.default_account_id
            or self.journal_id.suspense_account_id
        )

    def _l10n_ve_ensure_retention_outstanding_account(self):
        for payment in self:
            if payment.outstanding_account_id:
                continue
            outstanding = payment._l10n_ve_get_retention_outstanding_account()
            if outstanding:
                payment.outstanding_account_id = outstanding
        return self
