# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HrPayslipPaymentRegister(models.TransientModel):
    _name = "hr.payslip.payment.register"
    _description = "Register Payroll Payment"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        related="company_id.currency_id",
    )
    journal_id = fields.Many2one(
        "account.journal",
        string="Payment Journal",
        required=True,
        domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id)]",
        check_company=True,
    )
    payment_date = fields.Date(
        string="Payment Date",
        required=True,
        default=fields.Date.context_today,
    )
    communication = fields.Char(
        string="Memo",
    )
    line_ids = fields.One2many(
        "hr.payslip.payment.register.line",
        "wizard_id",
        string="Payslips",
    )
    amount_total = fields.Monetary(
        compute="_compute_amount_total",
        currency_field="currency_id",
    )

    @api.depends("line_ids.amount")
    def _compute_amount_total(self):
        for wizard in self:
            wizard.amount_total = sum(wizard.line_ids.mapped("amount"))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        payslips = self._get_payslips_from_context()
        if not payslips:
            return res
        companies = payslips.mapped("company_id")
        if len(companies) > 1:
            raise UserError(_("Select payslips from a single company."))
        company = companies
        res["company_id"] = company.id
        journal = self.env["account.journal"].search(
            [
                ("type", "in", ("bank", "cash")),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        if journal:
            res["journal_id"] = journal.id
        res["communication"] = _("Payroll payment")
        res["line_ids"] = [
            (
                0,
                0,
                {
                    "payslip_id": payslip.id,
                    "amount": payslip.l10n_ve_amount_residual,
                },
            )
            for payslip in payslips
            if not company.currency_id.is_zero(payslip.l10n_ve_amount_residual)
        ]
        return res

    @api.model
    def _get_payslips_from_context(self):
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids") or []
        if active_model == "hr.payslip" and active_ids:
            return self.env["hr.payslip"].browse(active_ids)
        if active_model == "hr.payslip.run" and active_ids:
            runs = self.env["hr.payslip.run"].browse(active_ids)
            return runs.mapped("slip_ids")
        return self.env["hr.payslip"]

    def action_create_payments(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Add at least one payslip to pay."))
        if not self.journal_id.default_account_id:
            raise UserError(
                _('Journal "%s" has no default account configured.')
                % self.journal_id.display_name
            )
        moves = self.env["account.move"]
        for line in self.line_ids:
            if self.currency_id.is_zero(line.amount):
                continue
            if self.currency_id.compare_amounts(
                line.amount, line.amount_residual
            ) > 0:
                raise UserError(
                    _(
                        "Payment amount for %(employee)s (%(amount)s) exceeds "
                        "the amount due (%(due)s)."
                    )
                    % {
                        "employee": line.employee_id.display_name,
                        "amount": line.amount,
                        "due": line.amount_residual,
                    }
                )
            move = self._create_payment_move(line)
            line.payslip_id.l10n_ve_payment_move_ids = [(4, move.id)]
            line.payslip_id._l10n_ve_mark_paid_state()
            moves |= move
        if not moves:
            raise UserError(_("Nothing to pay: all amounts are zero."))
        return {
            "name": _("Payroll Payments"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("id", "in", moves.ids)],
        }

    def _create_payment_move(self, line):
        self.ensure_one()
        payslip = line.payslip_id
        payable_account = payslip._l10n_ve_get_payroll_payable_account()
        if not payable_account:
            raise UserError(
                _(
                    "Payroll payable account 2103020 was not found for company %s."
                )
                % payslip.company_id.display_name
            )
        partner = payslip._l10n_ve_get_payment_partner()
        liquidity_account = self.journal_id.default_account_id
        amount = self.currency_id.round(line.amount)
        memo = self.communication or _("Payroll payment %s") % (
            payslip.number or payslip.display_name
        )
        move = self.env["account.move"].create(
            {
                "move_type": "entry",
                "date": self.payment_date,
                "journal_id": self.journal_id.id,
                "ref": payslip.number or payslip.name,
                "narration": memo,
                "company_id": self.company_id.id,
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": memo,
                            "account_id": payable_account.id,
                            "partner_id": partner.id if partner else False,
                            "debit": amount,
                            "credit": 0.0,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": memo,
                            "account_id": liquidity_account.id,
                            "partner_id": partner.id if partner else False,
                            "debit": 0.0,
                            "credit": amount,
                        },
                    ),
                ],
            }
        )
        move.action_post()
        self._reconcile_payable_lines(payslip, move, payable_account)
        return move

    def _reconcile_payable_lines(self, payslip, payment_move, payable_account):
        if not payslip.move_id or payslip.move_id.state != "posted":
            return
        lines = (
            payslip.move_id.line_ids | payment_move.line_ids
        ).filtered(
            lambda move_line: move_line.account_id == payable_account
            and not move_line.reconciled
            and not move_line.company_currency_id.is_zero(
                move_line.amount_residual
            )
        )
        if len(lines) >= 2:
            lines.reconcile()


class HrPayslipPaymentRegisterLine(models.TransientModel):
    _name = "hr.payslip.payment.register.line"
    _description = "Register Payroll Payment Line"

    wizard_id = fields.Many2one(
        "hr.payslip.payment.register",
        required=True,
        ondelete="cascade",
    )
    payslip_id = fields.Many2one(
        "hr.payslip",
        string="Payslip",
        required=True,
        ondelete="cascade",
    )
    employee_id = fields.Many2one(
        related="payslip_id.employee_id",
    )
    currency_id = fields.Many2one(
        related="wizard_id.currency_id",
    )
    amount_residual = fields.Monetary(
        string="Amount Due",
        related="payslip_id.l10n_ve_amount_residual",
        currency_field="currency_id",
    )
    amount = fields.Monetary(
        string="Amount to Pay",
        required=True,
        currency_field="currency_id",
    )
