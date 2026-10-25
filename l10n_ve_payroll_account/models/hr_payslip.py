# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    l10n_ve_payment_move_ids = fields.Many2many(
        "account.move",
        "hr_payslip_l10n_ve_payment_move_rel",
        "payslip_id",
        "move_id",
        string="Payroll Payment Entries",
        copy=False,
        readonly=True,
    )
    l10n_ve_payment_move_count = fields.Integer(
        compute="_compute_l10n_ve_payment_amounts",
    )
    l10n_ve_amount_net = fields.Monetary(
        string="Net to Pay",
        compute="_compute_l10n_ve_payment_amounts",
        currency_field="company_currency_id",
        help="Balance of payroll payable (2103020) from the payslip journal entry, "
        "not the TOTAL salary rule (avoids multicurrency rounding drift).",
    )
    l10n_ve_amount_paid = fields.Monetary(
        string="Amount Paid",
        compute="_compute_l10n_ve_payment_amounts",
        currency_field="company_currency_id",
    )
    l10n_ve_amount_residual = fields.Monetary(
        string="Amount Due",
        compute="_compute_l10n_ve_payment_amounts",
        currency_field="company_currency_id",
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Company Currency",
    )
    l10n_ve_payment_state = fields.Selection(
        selection=[
            ("not_paid", "Not Paid"),
            ("in_payment", "In Payment"),
            ("paid", "Paid"),
            ("reversed", "Reversed"),
        ],
        string="Payment Status",
        compute="_compute_l10n_ve_payment_state",
    )

    @api.depends(
        "line_ids.total",
        "line_ids.total_company_currency",
        "line_ids.code",
        "move_id",
        "move_id.line_ids.debit",
        "move_id.line_ids.credit",
        "move_id.state",
        "l10n_ve_payment_move_ids",
        "l10n_ve_payment_move_ids.line_ids.debit",
        "l10n_ve_payment_move_ids.state",
        "is_multicurrency",
        "company_id",
    )
    def _compute_l10n_ve_payment_amounts(self):
        for payslip in self:
            net = payslip._l10n_ve_get_net_to_pay()
            paid = payslip._l10n_ve_get_amount_paid()
            currency = payslip.company_id.currency_id
            residual = currency.round(net - paid) if currency else net - paid
            if currency and currency.compare_amounts(residual, 0.0) < 0:
                residual = 0.0
            payslip.l10n_ve_amount_net = net
            payslip.l10n_ve_amount_paid = paid
            payslip.l10n_ve_amount_residual = residual
            payslip.l10n_ve_payment_move_count = len(payslip.l10n_ve_payment_move_ids)

    @api.depends(
        "state",
        "paid",
        "credit_note",
        "refunded_id",
        "l10n_ve_amount_net",
        "l10n_ve_amount_paid",
        "l10n_ve_amount_residual",
        "company_id",
    )
    def _compute_l10n_ve_payment_state(self):
        for payslip in self:
            currency = payslip.company_id.currency_id
            if payslip.credit_note or payslip.refunded_id:
                payslip.l10n_ve_payment_state = "reversed"
            elif payslip.state != "done":
                payslip.l10n_ve_payment_state = "not_paid"
            elif payslip.paid or (
                currency and currency.is_zero(payslip.l10n_ve_amount_residual)
            ):
                payslip.l10n_ve_payment_state = "paid"
            elif currency and currency.compare_amounts(
                payslip.l10n_ve_amount_paid, 0.0
            ) > 0:
                payslip.l10n_ve_payment_state = "in_payment"
            else:
                payslip.l10n_ve_payment_state = "not_paid"

    def _l10n_ve_get_payable_balance_from_move(self):
        """Company-currency credit-debit on 2103020 from the payslip accrual move."""
        self.ensure_one()
        account = self._l10n_ve_get_payroll_payable_account()
        if not account or not self.move_id or self.move_id.state != "posted":
            return None
        lines = self.move_id.line_ids.filtered(
            lambda move_line: move_line.account_id == account
        )
        return sum(lines.mapped("credit")) - sum(lines.mapped("debit"))

    def _l10n_ve_get_net_to_pay(self):
        """Amount that must leave the bank: accounting payable, not rule TOTAL.

        Multicurrency payslips round each move line; sum(2103020) can differ
        from the TOTAL line by 0.01. Payment must clear the journal balance.
        """
        self.ensure_one()
        balance = self._l10n_ve_get_payable_balance_from_move()
        if balance is not None:
            currency = self.company_id.currency_id
            if currency.compare_amounts(balance, 0.0) < 0:
                return 0.0
            return currency.round(balance)
        line = self.line_ids.filtered(lambda slip_line: slip_line.code == "TOTAL")[:1]
        if not line:
            return 0.0
        if self.is_multicurrency:
            return abs(line.total_company_currency)
        return abs(line.total)

    def _l10n_ve_get_amount_paid(self):
        self.ensure_one()
        account = self._l10n_ve_get_payroll_payable_account()
        if not account:
            return 0.0
        moves = self.l10n_ve_payment_move_ids.filtered(
            lambda move: move.state == "posted"
        )
        lines = moves.line_ids.filtered(
            lambda move_line: move_line.account_id == account and move_line.debit
        )
        return sum(lines.mapped("debit"))

    def _l10n_ve_get_payroll_payable_account(self):
        self.ensure_one()
        chart = self.env["account.chart.template"].with_company(self.company_id)
        return chart._l10n_ve_payroll_find_account(
            self.company_id,
            "account_account_2103020",
            "2103020",
        )

    def _l10n_ve_get_payment_partner(self):
        self.ensure_one()
        return self.employee_id.work_contact_id

    def action_l10n_ve_register_payment(self):
        payslips = self.filtered(lambda slip: slip.state == "done")
        if not payslips:
            raise UserError(_("Only confirmed payslips can be paid."))
        unpaid = payslips.filtered(
            lambda slip: not slip.company_id.currency_id.is_zero(
                slip.l10n_ve_amount_residual
            )
        )
        if not unpaid:
            raise UserError(_("Selected payslips are already fully paid."))
        return {
            "name": _("Register Payroll Payment"),
            "type": "ir.actions.act_window",
            "res_model": "hr.payslip.payment.register",
            "view_mode": "form",
            "target": "new",
            "context": {
                "active_model": "hr.payslip",
                "active_ids": unpaid.ids,
            },
        }

    def action_open_l10n_ve_payment_moves(self):
        self.ensure_one()
        return {
            "name": _("Payroll Payments"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", self.l10n_ve_payment_move_ids.ids)],
            "context": {"create": False},
        }

    def _l10n_ve_mark_paid_state(self):
        for payslip in self:
            currency = payslip.company_id.currency_id
            is_paid = currency.is_zero(payslip.l10n_ve_amount_residual)
            if payslip.paid != is_paid:
                payslip.paid = is_paid
