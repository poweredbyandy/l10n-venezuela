# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


class AccountPaymentClosing(models.Model):
    _name = "account.payment.closing"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Payment Terminal Closing"
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        default="/",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    journal_id = fields.Many2one(
        comodel_name="account.journal",
        required=True,
        tracking=True,
        check_company=True,
        domain="[('type', 'in', ('bank', 'cash', 'credit'))]",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_currency_id",
    )
    date = fields.Date(
        required=True,
        tracking=True,
        default=fields.Date.context_today,
        help="Date of the payments included in the closing.",
    )
    deposit_date = fields.Date(
        string="Bank Credit Date",
        compute="_compute_deposit_date",
        store=True,
        precompute=True,
        readonly=False,
        required=True,
        tracking=True,
        help="Date the bank credits the closing. The journal entry uses this "
        "date so it matches the bank transaction.",
    )
    payment_method_line_ids = fields.Many2many(
        comodel_name="account.payment.method.line",
        string="Payment Methods",
        domain="[('journal_id', '=', journal_id)]",
        help="Leave empty to include every payment method of the journal.",
    )
    payment_ids = fields.One2many(
        comodel_name="account.payment",
        inverse_name="closing_id",
        string="Payments",
        readonly=True,
    )
    payment_count = fields.Integer(compute="_compute_amount_total")
    amount_total = fields.Monetary(
        compute="_compute_amount_total",
        currency_field="currency_id",
    )
    outstanding_account_id = fields.Many2one(
        comodel_name="account.account",
        compute="_compute_outstanding_account_id",
        store=True,
        readonly=False,
        check_company=True,
        help="Account of the single open line matched with the bank transaction.",
    )
    move_id = fields.Many2one(
        comodel_name="account.move",
        string="Journal Entry",
        readonly=True,
        copy=False,
        check_company=True,
    )
    closing_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Closing Item",
        readonly=True,
        copy=False,
        check_company=True,
        help="Journal item left open to be matched with the bank transaction.",
    )
    is_matched = fields.Boolean(
        string="Matched With Bank",
        compute="_compute_is_matched",
        store=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("posted", "Posted"),
            ("cancel", "Cancelled"),
        ],
        required=True,
        readonly=True,
        copy=False,
        tracking=True,
        default="draft",
    )

    @api.depends("journal_id", "company_id")
    def _compute_currency_id(self):
        for closing in self:
            closing.currency_id = (
                closing.journal_id.currency_id or closing.company_id.currency_id
            )

    @api.depends("date")
    def _compute_deposit_date(self):
        for closing in self:
            if not closing.deposit_date or closing.deposit_date < closing.date:
                closing.deposit_date = closing.date

    @api.depends("payment_ids.amount_signed")
    def _compute_amount_total(self):
        for closing in self:
            closing.payment_count = len(closing.payment_ids)
            closing.amount_total = sum(closing.payment_ids.mapped("amount_signed"))

    @api.depends("payment_ids.outstanding_account_id", "payment_ids.amount_signed")
    def _compute_outstanding_account_id(self):
        for closing in self:
            totals = defaultdict(float)
            for payment in closing.payment_ids:
                totals[payment.outstanding_account_id] += payment.amount_signed
            closing.outstanding_account_id = (
                max(totals, key=lambda account: abs(totals[account]))
                if totals
                else False
            )

    @api.depends("closing_line_id.reconciled")
    def _compute_is_matched(self):
        for closing in self:
            closing.is_matched = closing.closing_line_id.reconciled

    @api.constrains("date", "deposit_date")
    def _check_deposit_date(self):
        for closing in self:
            if closing.deposit_date < closing.date:
                raise ValidationError(
                    _("The bank credit date cannot be before the closing date.")
                )

    @api.onchange("journal_id")
    def _onchange_journal_id(self):
        self.payment_method_line_ids = False

    @api.ondelete(at_uninstall=False)
    def _unlink_except_posted(self):
        if any(closing.state == "posted" for closing in self):
            raise UserError(_("You cannot delete a posted closing."))

    def _get_payment_search_domain(self):
        self.ensure_one()
        domain = [
            ("company_id", "=", self.company_id.id),
            ("journal_id", "=", self.journal_id.id),
            ("date", "=", self.date),
            ("state", "in", ("in_process", "paid")),
            ("move_id", "!=", False),
            ("outstanding_account_id", "!=", False),
            ("is_matched", "=", False),
            "|",
            ("closing_id", "=", False),
            ("closing_id", "=", self.id),
        ]
        method_domains = self._get_payment_method_domains()
        if method_domains:
            domain = expression.AND([domain, expression.OR(method_domains)])
        return domain

    def _get_payment_method_domains(self):
        """Return the domains identifying the terminal; any of them matches."""
        self.ensure_one()
        if not self.payment_method_line_ids:
            return []
        return [[("payment_method_line_id", "in", self.payment_method_line_ids.ids)]]

    def action_search_payments(self):
        for closing in self:
            if closing.state != "draft":
                raise UserError(_("Only draft closings can search payments."))
            payments = self.env["account.payment"].search(
                closing._get_payment_search_domain()
            )
            if not payments:
                raise UserError(
                    _(
                        "No pending payments were found for %(journal)s on %(date)s.",
                        journal=closing.journal_id.display_name,
                        date=closing.date,
                    )
                )
            (closing.payment_ids - payments).closing_id = False
            payments.closing_id = closing
        return True

    def _get_payment_liquidity_lines(self, payment):
        liquidity_lines = payment._seek_for_lines()[0]
        return liquidity_lines.filtered(
            lambda line: line.account_id == payment.outstanding_account_id
            and not line.reconciled
        )

    def _check_payments_before_post(self):
        self.ensure_one()
        if not self.payment_ids:
            raise UserError(_("Add at least one payment before posting the closing."))
        if self.currency_id.is_zero(self.amount_total):
            raise UserError(_("The closing total cannot be zero."))
        invalid = self.payment_ids.filtered(
            lambda pay: pay.is_matched
            or pay.journal_id != self.journal_id
            or pay.move_id.state != "posted"
            or not self._get_payment_liquidity_lines(pay)
        )
        if invalid:
            raise UserError(
                _(
                    "These payments are no longer pending and cannot be closed:\n"
                    "%(payments)s",
                    payments="\n".join(invalid.mapped("display_name")),
                )
            )
        if not self.outstanding_account_id:
            raise UserError(_("Set the outstanding account of the closing."))
        not_reconcilable = (
            self.payment_ids.outstanding_account_id | self.outstanding_account_id
        ).filtered(lambda account: not account.reconcile)
        if not_reconcilable:
            raise UserError(
                _(
                    "The outstanding account %(accounts)s must allow reconciliation.",
                    accounts=", ".join(not_reconcilable.mapped("display_name")),
                )
            )

    def _prepare_move_line_vals(self, liquidity_lines):
        """Return the counterpart values of each payment and the values of
        the single open line that will be matched with the bank.
        """
        self.ensure_one()
        counterpart_vals = []
        amount_currency = balance = 0.0
        for payment in self.payment_ids:
            for line in liquidity_lines.filtered(
                lambda aml, payment=payment: aml.payment_id == payment
            ):
                counterpart_vals.append(
                    {
                        "name": payment.memo or payment.name,
                        "account_id": line.account_id.id,
                        "partner_id": line.partner_id.id,
                        "currency_id": line.currency_id.id,
                        "amount_currency": -line.amount_residual_currency,
                        "balance": -line.amount_residual,
                    }
                )
                amount_currency += line.amount_residual_currency
                balance += line.amount_residual
        closing_vals = {
            "name": self.name,
            "account_id": self.outstanding_account_id.id,
            "currency_id": self.currency_id.id,
            "amount_currency": amount_currency,
            "balance": balance,
        }
        return counterpart_vals, closing_vals

    def _prepare_move_vals(self, line_vals):
        self.ensure_one()
        return {
            "move_type": "entry",
            "journal_id": self.journal_id.id,
            "company_id": self.company_id.id,
            "date": self.deposit_date,
            "ref": self.name,
            "line_ids": [Command.create(vals) for vals in line_vals],
        }

    def action_post(self):
        for closing in self:
            if closing.state != "draft":
                raise UserError(_("Only draft closings can be posted."))
            closing._check_payments_before_post()
            if closing.name == "/":
                closing.name = self.env["ir.sequence"].next_by_code(
                    "account.payment.closing"
                )
            liquidity_lines = self.env["account.move.line"]
            for payment in closing.payment_ids:
                liquidity_lines |= closing._get_payment_liquidity_lines(payment)
            counterpart_vals, closing_vals = closing._prepare_move_line_vals(
                liquidity_lines
            )
            move = self.env["account.move"].create(
                closing._prepare_move_vals(counterpart_vals + [closing_vals])
            )
            move.action_post()
            move_lines = move.line_ids.sorted("id")
            counterpart_lines = move_lines[: len(counterpart_vals)]
            for account in liquidity_lines.account_id:
                (liquidity_lines | counterpart_lines).filtered(
                    lambda aml, account=account: aml.account_id == account
                ).reconcile()
            closing.write(
                {
                    "move_id": move.id,
                    "closing_line_id": (move_lines - counterpart_lines).id,
                    "state": "posted",
                }
            )
        return True

    def action_draft(self):
        for closing in self:
            line = closing.closing_line_id
            if line.matched_debit_ids or line.matched_credit_ids:
                raise UserError(
                    _(
                        "Closing %(name)s is already matched with a bank transaction. "
                        "Unreconcile it first.",
                        name=closing.name,
                    )
                )
            if closing.move_id:
                closing.move_id.button_draft()
                closing.move_id.button_cancel()
            closing.write(
                {
                    "move_id": False,
                    "closing_line_id": False,
                    "state": "draft",
                }
            )
        return True

    def action_cancel(self):
        if any(closing.state == "posted" for closing in self):
            raise UserError(_("Reset the closing to draft before cancelling it."))
        self.payment_ids.closing_id = False
        self.state = "cancel"
        return True

    def action_open_move(self):
        self.ensure_one()
        return self.move_id._get_records_action(name=_("Journal Entry"))

    def action_open_payments(self):
        self.ensure_one()
        return self.payment_ids._get_records_action(name=_("Payments"))
