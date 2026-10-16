from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from ..utils.utils_retention import load_retention_lines

RETENTION_TYPES = [
    ("islr", "ISLR"),
    ("iva", "IVA"),
    ("municipal", "Municipal"),
]

# Fields of the wizard that only make sense when the payment is a retention.
# They must never keep a value when the payment is not a retention.
RETENTION_ONLY_FIELDS = (
    "retention_type",
    "voucher_date",
    "retention_ref",
    "retention_line_ids",
)


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    is_out_invoice = fields.Boolean()
    is_retention = fields.Boolean(string="Retention payment", default=False)
    retention_type = fields.Selection(
        RETENTION_TYPES,
        string="Retention type",
        help="Type of retention that applies to this payment.",
    )
    edit_retention_fields = fields.Boolean(default=True)

    voucher_date = fields.Date(
        "Fecha Comprobante",
        help="Date of issuance of the withholding voucher by the external party.",
    )
    retention_ref = fields.Char(string="Retention reference")

    retention_line_ids = fields.Many2many("account.retention.line")

    # -------------------------------------------------------------------------
    # CRUD: never keep retention data in a payment that is not a retention
    # -------------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        sanitized_vals_list = []
        for vals in vals_list:
            if not vals.get("is_retention"):
                vals = {k: v for k, v in vals.items() if k != "retention_line_ids"}
                vals.update(
                    retention_type=False,
                    voucher_date=False,
                    retention_ref=False,
                    edit_retention_fields=True,
                )
            sanitized_vals_list.append(vals)
        return super().create(sanitized_vals_list)

    def write(self, vals):
        res = super().write(vals)
        if "is_retention" in vals or any(f in vals for f in RETENTION_ONLY_FIELDS):
            self._clear_retention_data()
        return res

    def unlink(self):
        # The lines created by the wizard that never reached a retention
        # record would stay as orphan data otherwise.
        self.retention_line_ids.filtered(lambda line: not line.retention_id).unlink()
        return super().unlink()

    def _clear_retention_data(self):
        """
        Wipes all the retention data of the wizards that are not a retention
        payment, so no garbage is left when the user unchecks the retention
        option after having filled it.
        """
        wizards = self.filtered(
            lambda w: not w.is_retention
            and (
                w.retention_type
                or w.retention_line_ids
                or w.voucher_date
                or w.retention_ref
            )
        )
        for wizard in wizards:
            orphan_lines = wizard.retention_line_ids.filtered(
                lambda line: not line.retention_id
            )
            wizard.write(
                {
                    "retention_type": False,
                    "voucher_date": False,
                    "retention_ref": False,
                    "retention_line_ids": [Command.clear()],
                    "edit_retention_fields": True,
                }
            )
            orphan_lines.unlink()

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------

    @api.depends(
        "early_payment_discount_mode",
        "can_edit_wizard",
        "can_group_payments",
        "group_payment",
        "payment_method_line_id",
        "is_retention",
    )
    def _compute_show_payment_difference(self):
        wizards = self.env["account.payment.register"]
        for wizard in self:
            if wizard.is_retention:
                wizard.show_payment_difference = False
                wizards |= wizard

        return super(
            AccountPaymentRegister, self - wizards
        )._compute_show_payment_difference()

    @api.depends("is_retention", "retention_line_ids.retention_amount")
    def _compute_amount(self):
        """
        The amount of a retention payment is always the sum of the current
        retention lines. If there are no lines yet, the amount is 0 so a
        previous type or a previous check does not leave a leftover total.
        """
        retention_wizards = self.filtered("is_retention")
        for wizard in retention_wizards:
            wizard.amount = sum(wizard.retention_line_ids.mapped("retention_amount"))
        return super(AccountPaymentRegister, self - retention_wizards)._compute_amount()

    @api.depends("installments_mode", "is_retention")
    def _compute_installments_switch_values(self):
        """
        A retention is never paid in installments: the switch (that would
        replace the retention amount by the amount of the invoice) is removed.
        """
        super()._compute_installments_switch_values()
        for wizard in self.filtered("is_retention"):
            wizard.installments_switch_html = False
            wizard.installments_switch_amount = 0.0

    @api.depends(
        "payment_type",
        "company_id",
        "can_edit_wizard",
        "is_retention",
        "retention_type",
    )
    def _compute_available_journal_ids(self):
        """
        Ensure that retention journals are not selectable when registering
        payments. When the payment is a retention, the journal of that type
        stays available so it can be shown as the locked value.
        """
        res = super()._compute_available_journal_ids()
        retention_journal_ids = tuple(
            journal.id for journal in self._get_all_retention_journals()
        )
        for wizard in self:
            wizard.available_journal_ids = wizard.available_journal_ids.filtered_domain(
                [("id", "not in", retention_journal_ids)]
            )
            if wizard.is_retention:
                wizard.available_journal_ids |= wizard._get_customer_retention_journal()
        return res

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _get_all_retention_journals(self):
        company = self.env.company
        return (
            company.iva_supplier_retention_journal_id
            | company.iva_customer_retention_journal_id
            | company.islr_supplier_retention_journal_id
            | company.islr_customer_retention_journal_id
            | company.municipal_supplier_retention_journal_id
            | company.municipal_customer_retention_journal_id
        )

    def _get_customer_retention_journal(self, retention_type=None):
        """Journal used for the customer retention of the given type."""
        company = self.company_id or self.env.company
        journals = {
            "iva": company.iva_customer_retention_journal_id,
            "islr": company.islr_customer_retention_journal_id,
            "municipal": company.municipal_customer_retention_journal_id,
        }
        return journals.get(
            retention_type or self.retention_type, self.env["account.journal"]
        )

    def _get_retention_type_label(self, retention_type=None):
        retention_type = retention_type or self.retention_type
        return dict(RETENTION_TYPES).get(retention_type, "")

    def _get_retention_invoices(self):
        """Invoices that are being paid with this wizard."""
        invoices = self.line_ids.move_id
        if not invoices and self._context.get("active_model") == "account.move":
            invoices = self.env["account.move"].browse(
                self._context.get("active_ids") or []
            )
        return invoices

    @api.model
    def _get_retention_lines_field(self, retention_type):
        return {
            "iva": "retention_iva_line_ids",
            "islr": "retention_islr_line_ids",
            "municipal": "retention_municipal_line_ids",
        }[retention_type]

    def _get_invoices_with_active_retention(self, invoices, retention_type):
        lines_field = self._get_retention_lines_field(retention_type)
        return invoices.filtered(
            lambda invoice: any(
                line.state in ("draft", "emitted") for line in invoice[lines_field]
            )
        )

    def _warning_reset_retention_type(self, message):
        """
        Onchange result that shows an error and resets the retention type, so
        nothing about the retention is kept.
        """
        self._reset_retention_payment_values()
        return {
            "warning": {"title": _("Error"), "message": message},
            "value": {
                "retention_type": False,
                "retention_line_ids": [Command.clear()],
                "amount": 0.0,
            },
        }

    def _discard_wizard_retention_lines(self):
        """
        Drops the wizard lines completely. Command.clear() alone can leave
        NewId records in the onchange cache, and those leftovers are summed
        into the payment amount the next time the user edits a line.
        """
        self.ensure_one()
        lines = self.retention_line_ids
        self.retention_line_ids = False
        persisted_orphans = lines.filtered(
            lambda line: line.id
            and not isinstance(line.id, models.NewId)
            and not line.retention_id
        )
        if persisted_orphans:
            persisted_orphans.unlink()

    def _clear_custom_payment_amount(self):
        """
        The standard payment wizard stores a typed amount in custom_user_amount.
        Setting the retention total would be treated as a typed amount and then
        kept (or added) on the next change. Wipe it every time the retention
        total is rebuilt.
        """
        self.custom_user_amount = False
        self.custom_user_currency_id = False

    def _set_retention_payment_amount(self):
        """Replace the payment amount with the sum of the current lines."""
        self._clear_custom_payment_amount()
        if self.is_retention:
            self.amount = sum(self.retention_line_ids.mapped("retention_amount"))
        else:
            self._compute_amount()

    # -------------------------------------------------------------------------
    # Onchanges
    # -------------------------------------------------------------------------

    def _reset_retention_payment_values(self):
        """
        Removes the retention lines and the leftover payment amount. If the
        payment is no longer a retention, restore the normal payment amount
        and journal.
        """
        self._discard_wizard_retention_lines()
        self.edit_retention_fields = True
        self._clear_custom_payment_amount()
        if self.is_retention:
            self.amount = 0.0
            return
        self._compute_journal_id()
        self._compute_amount()

    @api.onchange("is_retention")
    def _onchange_retention(self):
        """
        When the payment is marked as a retention the user must choose which
        retention applies, so we start from a clean state.

        If the payment is not (or no longer) a retention, we clear everything
        related to the retention (type, voucher data and lines) and give the
        payment its regular values back, so the user can edit the payment fields.
        """
        if not self.is_retention:
            self.retention_type = False
            self.voucher_date = False
            self.retention_ref = False
            self._reset_retention_payment_values()
            return
        self._reset_retention_payment_values()
        self.retention_type = False
        if self.can_group_payments:
            self.group_payment = False

    @api.onchange("retention_type")
    def _onchange_retention_type(self):
        """
        Sets the journal for the customer retention of the selected type and
        loads the retention lines from the invoices.

        If the type is cleared, or the payment is not a retention, the lines
        and the values locked by the retention are discarded.
        """
        self._discard_wizard_retention_lines()
        self._clear_custom_payment_amount()
        self.amount = 0.0
        if not self.is_retention or not self.retention_type:
            self._reset_retention_payment_values()
            return
        journal = self._get_customer_retention_journal()
        if not journal:
            return self._warning_reset_retention_type(
                _(
                    "The company must have a customer %(type)s retention journal "
                    "configured.",
                    type=self._get_retention_type_label(),
                )
            )
        result = self._load_retention_lines(self._get_retention_invoices())
        if result.get("warning"):
            return result
        if self.can_group_payments:
            self.group_payment = False
        self.journal_id = journal.id
        self.edit_retention_fields = False
        self.retention_line_ids = result["value"]["retention_line_ids"]
        self._set_retention_payment_amount()

    @api.onchange("amount")
    def _onchange_amount(self):
        if self.is_retention:
            self._clear_custom_payment_amount()
            return
        return super()._onchange_amount()

    @api.onchange("payment_date")
    def _onchange_payment_date(self):
        if self.is_retention:
            return
        return super()._onchange_payment_date()

    @api.onchange("currency_id")
    def _onchange_currency_id(self):
        if self.is_retention:
            return
        return super()._onchange_currency_id()

    def _load_retention_lines(self, invoices):
        """
        Loads the retention lines of the selected retention type from the
        invoices.

        Returns
        -------
        dict
            The onchange values containing the lines to be loaded or the errors.
        """
        if not invoices or any(
            move_type not in ("out_invoice", "out_refund")
            for move_type in invoices.mapped("move_type")
        ):
            return self._warning_reset_retention_type(
                _("Retention payments can only be registered for customer invoices.")
            )
        invoices_with_retention = self._get_invoices_with_active_retention(
            invoices, self.retention_type
        )
        if invoices_with_retention:
            return self._warning_reset_retention_type(
                _(
                    "You can't create a %(type)s retention payment for the invoices "
                    "selected because one or more of them already have an "
                    "emitted retention.",
                    type=self._get_retention_type_label(),
                )
            )
        loaders = {
            "iva": self._load_iva_retention_lines,
            "islr": self._load_islr_retention_lines,
            "municipal": self._load_municipal_retention_lines,
        }
        return loaders[self.retention_type](invoices)

    def _load_iva_retention_lines(self, invoices):
        """
        Loads the retention lines from the invoices when the retention payment
        to register is of type IVA.

        If any of the invoices selected doesn't have any tax line, we return an
        error.

        Parameters
        ----------
        invoices : recordset of account.move
            The invoices to load the retention lines from.

        Returns
        -------
        dict
            The onchange values containing the lines to be loaded or the errors.
        """
        invoices_without_taxes = invoices.filtered(
            lambda i: not any(
                line.tax_ids[0].amount > 0 for line in i.line_ids if line.tax_ids
            )
        )
        if any(invoices_without_taxes):
            return self._warning_reset_retention_type(
                _(
                    "You can't create a retention payment for the invoices selected because "  # noqa: E501
                    "one or more of them don't have any tax line."
                )
            )

        retention_lines = []
        for invoice in invoices:
            retention_lines.extend(
                load_retention_lines(invoice, self.env["account.retention"])
            )
        for command in retention_lines:
            vals = command[2]
            vals["retention_amount"] = vals.get("iva_amount", 0.0) * (
                vals.get("related_percentage_tax_base", 0.0) / 100.0
            )
        return {"value": {"retention_line_ids": retention_lines}}

    def _prepare_manual_retention_line_vals(self, invoice, name, invoice_amount):
        """
        Values of a retention line whose retained amount is typed by the user
        (ISLR and municipal customer payments).
        """
        return {
            "name": name,
            "invoice_type": invoice.move_type,
            "move_id": invoice.id,
            "invoice_total": abs(invoice.amount_total_signed),
            "invoice_amount": invoice_amount,
            "retention_amount": 0.0,
        }

    def _load_islr_retention_lines(self, invoices):
        """
        Loads one retention line per invoice for an ISLR retention. The user
        must choose the payment concept and type the retained amount.
        """
        retention_lines = [
            Command.create(
                self._prepare_manual_retention_line_vals(
                    invoice,
                    _("ISLR Retention"),
                    invoice._l10n_ve_get_positive_tax_base_amount()
                    or abs(invoice.amount_untaxed_signed),
                )
            )
            for invoice in invoices
        ]
        return {"value": {"retention_line_ids": retention_lines}}

    def _load_municipal_retention_lines(self, invoices):
        """
        Loads one retention line per invoice for a municipal retention. The user
        must choose the economic activity and type the retained amount.
        """
        retention_lines = []
        for invoice in invoices:
            product_lines = invoice.invoice_line_ids.filtered(
                lambda line: line.display_type == "product"
            )
            partner = invoice._l10n_ve_withholding_partner()
            vals = self._prepare_manual_retention_line_vals(
                invoice,
                _("Municipal Retention"),
                invoice._l10n_ve_sum_lines_company_base(product_lines),
            )
            if partner.economic_activity_id:
                vals["economic_activity_id"] = partner.economic_activity_id.id
                vals["aliquot"] = partner.economic_activity_id.aliquot
            retention_lines.append(Command.create(vals))
        return {"value": {"retention_line_ids": retention_lines}}

    @api.onchange("retention_line_ids")
    def _onchange_retention_line_ids(self):
        """
        If the retention lines change, we compute the amount of the payment
        using their retention amounts.

        This is made just for the user to see the amount of the payment before
        posting it, as we compute the amount of the payment from the retention
        lines in the _init_payments method (this is due the fact that it can
        create multiple payments, if that wasn't the case, this onchange would
        suffice to compute the payment amount).
        """
        if not self.is_retention:
            return
        self._set_retention_payment_amount()

    # -------------------------------------------------------------------------
    # Validations
    # -------------------------------------------------------------------------

    def _validate_retention_data(self):
        """
        Validates the retention data before the payments are created.

        - If the payment is not a retention nothing about retentions is kept.
        - If it is, the type must be selected and the data required by that
          type of retention must be complete.
        """
        self._clear_retention_data()
        for wizard in self.filtered("is_retention"):
            wizard._validate_retention_payment()

    def _validate_retention_payment(self):
        self.ensure_one()
        if not self.retention_type:
            raise UserError(_("Select the type of retention that applies."))
        invoices = self._get_retention_invoices()
        if not invoices or any(
            move_type not in ("out_invoice", "out_refund")
            for move_type in invoices.mapped("move_type")
        ):
            raise UserError(
                _("Retention payments can only be registered for customer invoices.")
            )
        type_label = self._get_retention_type_label()
        if not self._get_customer_retention_journal():
            raise UserError(
                _(
                    "The company must have a customer %(type)s retention journal "
                    "configured.",
                    type=type_label,
                )
            )
        if not self.voucher_date or not self.retention_ref:
            raise UserError(
                _("The voucher date and the retention reference are required.")
            )
        if not self.retention_line_ids:
            raise UserError(_("There are no retention lines to register."))
        if any(not line.retention_amount for line in self.retention_line_ids):
            raise UserError(_("You can not create a retention with 0 amount."))
        if self._get_invoices_with_active_retention(invoices, self.retention_type):
            raise UserError(
                _(
                    "You can't create a %(type)s retention payment for the invoices "
                    "selected because one or more of them already have an "
                    "emitted retention.",
                    type=type_label,
                )
            )
        if self.retention_type == "islr":
            if not all(self.retention_line_ids.mapped("payment_concept_id")):
                raise UserError(_("Select a payment concept"))
            if any(
                not line.move_id._l10n_ve_withholding_partner().type_person_id
                for line in self.retention_line_ids
            ):
                raise UserError(_("Select a type person"))
        elif self.retention_type == "municipal":
            if not all(self.retention_line_ids.mapped("economic_activity_id")):
                raise UserError(_("Select an economic activity"))

    def _create_payments(self):
        self._validate_retention_data()
        return super()._create_payments()

    # -------------------------------------------------------------------------
    # Payments
    # -------------------------------------------------------------------------

    def _init_payments(self, to_process, edit_mode=False):
        """
        If the payment is a retention, we add the retention lines to the payment
        record, compute its amount with them, create the retention record and
        post it. This handles the payment post and reconciliation with the
        invoices.

        Returns
        -------
        recordset of account.payment
            The payments already posted and reconciled with the invoices.
        """
        payments = super()._init_payments(to_process, edit_mode)
        if not self.is_retention:
            return payments
        journal = self._get_customer_retention_journal()
        for payment, vals in zip(payments, to_process, strict=False):
            payment.is_retention = True
            payment.payment_type_retention = self.retention_type
            payment.retention_line_ids = [
                Command.link(line.id)
                for line in self.retention_line_ids
                if line.move_id == vals["to_reconcile"].move_id
            ]
            payment.journal_id = journal.id
            payment.compute_retention_amount_from_retention_lines()
        retention = self.with_context(skip_is_manually_modified=True)._create_retention(
            payments
        )
        retention.action_post()
        return payments

    def _post_payments(self, to_process, edit_mode=False):
        """
        If the payment is a retention, we avoid the post of the payment because
        we manage that in the retention action_post method.
        """
        return (
            super()._post_payments(to_process, edit_mode)
            if not self.is_retention
            else None
        )

    def _reconcile_payments(self, to_process, edit_mode=False):
        """
        If the payment is a retention, we avoid the reconciliation of the
        payment with the invoices because we manage that in the retention
        action_post method.
        """
        if self.is_retention:
            return
        return super()._reconcile_payments(to_process, edit_mode)

    def _create_retention(self, payments):
        """
        Creates the retention record from the payments records.

        Its retention type is the one selected in the wizard and its type is
        out_invoice, as it will always be a customer retention payment the one
        that is created through this wizard.

        Parameters
        ----------
        payments : recordset of account.payment
            The payments records that will be linked to the retention.

        Returns
        -------
        recordset of account.retention
            The retention record created.
        """
        retention = self.env["account.retention"].create(
            {
                "name": f"Retention {self._get_retention_type_label()}",
                "type_retention": self.retention_type,
                "date": self.voucher_date,
                "date_accounting": self.payment_date,
                "partner_id": self.partner_id.id,
                "company_id": self.company_id.id,
                "code": self.retention_ref,
                "number": self.retention_ref,
                "correlative": self.retention_ref,
                "type": "out_invoice",
                "payment_ids": payments.ids,
                "retention_line_ids": self.retention_line_ids.ids,
            }
        )
        return retention
