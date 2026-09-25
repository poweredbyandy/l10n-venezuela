import logging

from odoo import _, api, Command, fields, models

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
    retention_count = fields.Integer(
        compute="_compute_retention_count",
    )

    @api.depends("retention_id", "retention_line_ids.retention_id")
    def _compute_retention_count(self):
        for payment in self:
            payment.retention_count = len(
                payment.retention_id | payment.retention_line_ids.retention_id
            )

    def _l10n_ve_get_linked_retentions(self):
        self.ensure_one()
        return self.retention_id | self.retention_line_ids.retention_id

    def _l10n_ve_retention_form_view(self, retention):
        xmlids = {
            "iva": "l10n_ve_withholding.view_retention_iva_form_l10n_ve_withholding",
            "islr": "l10n_ve_withholding.view_retention_islr_form_l10n_ve_withholding",
            "municipal": (
                "l10n_ve_withholding.view_retention_municipal_form_l10n_ve_withholding"
            ),
        }
        xmlid = xmlids.get(retention.type_retention)
        if not xmlid:
            return False
        return self.env.ref(xmlid, raise_if_not_found=False)

    def action_view_retention(self):
        self.ensure_one()
        retentions = self._l10n_ve_get_linked_retentions()
        if not retentions:
            return False
        if len(retentions) > 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Retentions"),
                "res_model": "account.retention",
                "view_mode": "list,form",
                "domain": [("id", "in", retentions.ids)],
                "target": "current",
            }
        retention = retentions
        action = {
            "type": "ir.actions.act_window",
            "name": retention.display_name,
            "res_model": "account.retention",
            "res_id": retention.id,
            "view_mode": "form",
            "target": "current",
        }
        view = self._l10n_ve_retention_form_view(retention)
        if view:
            action["views"] = [(view.id, "form")]
        return action

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
