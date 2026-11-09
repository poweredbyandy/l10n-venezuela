# Part of Odoo. See LICENSE file for full copyright and licensing details.

from contextlib import contextmanager

from odoo import api, fields, models
from odoo.tools import float_compare, float_round

INVOICE_MOVE_TYPES = ("out_invoice", "in_invoice", "out_refund", "in_refund")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    price_subtotal_currency = fields.Monetary(
        string="Subtotal in Company Currency",
        compute="_compute_price_subtotal_currency",
        inverse="_inverse_price_subtotal_currency",
        currency_field="company_currency_id",
        store=True,
        precompute=True,
        readonly=False,
    )
    price_total_currency = fields.Monetary(
        string="Company Total",
        compute="_compute_price_total_currency",
        inverse="_inverse_price_total_currency",
        currency_field="company_currency_id",
        store=True,
        readonly=False,
    )
    price_unit_company_currency = fields.Float(
        string="Unit Price in Company Currency",
        compute="_compute_price_unit_company_currency",
        digits="Product Price",
    )
    manually_price_subtotal_currency = fields.Boolean(
        string="Manual Subtotal in Company Currency",
        default=False,
    )
    warning_rate_difference = fields.Boolean(
        string="Exchange Rate Warning",
        compute="_compute_warning_rate_difference",
        store=True,
    )
    has_rate_difference = fields.Boolean(
        string="Has Exchange Rate Difference",
        compute="_compute_has_rate_difference",
    )

    @api.depends(
        "quantity",
        "discount",
        "price_unit",
        "tax_ids",
        "currency_id",
        "display_type",
        "balance",
        "move_id.move_type",
        "move_id.state",
        "move_id.invoice_currency_rate",
        "manually_price_subtotal_currency",
    )
    def _compute_price_subtotal_currency(self):
        for line in self:
            if line.manually_price_subtotal_currency:
                line.price_subtotal_currency = (
                    line._origin.price_subtotal_currency
                    if line.id
                    else line.price_subtotal_currency
                )
                continue
            refund_subtotal = line._l10n_ve_draft_refund_company_subtotal()
            if refund_subtotal is not None:
                line.price_subtotal_currency = refund_subtotal
                continue
            move = line.move_id
            use_balance = (
                line.display_type == "product"
                and move.move_type in INVOICE_MOVE_TYPES
                and (
                    move.state == "posted"
                    or (
                        move.move_type in ("out_refund", "in_refund")
                        and move.reversed_entry_id
                        and move.currency_id != move.company_currency_id
                    )
                )
            )
            if use_balance:
                line.price_subtotal_currency = line.company_currency_id.round(
                    abs(line.balance)
                )
                continue
            line.price_subtotal_currency = line._l10n_ve_company_currency_subtotal()

    @api.depends(
        "price_total",
        "price_subtotal",
        "price_subtotal_currency",
        "currency_id",
        "display_type",
        "move_id.move_type",
        "move_id.invoice_currency_rate",
        "manually_price_subtotal_currency",
        "tax_ids",
    )
    def _compute_price_total_currency(self):
        for line in self:
            line.price_total_currency = line._l10n_ve_company_currency_total()

    def _inverse_price_subtotal_currency(self):
        for line in self:
            if (
                line.display_type != "product"
                or line.move_id.move_type not in INVOICE_MOVE_TYPES
            ):
                continue
            if self.env.context.get("l10n_ve_resetting_company_currency"):
                continue
            if line.company_currency_id.is_zero(line.price_subtotal_currency):
                line.manually_price_subtotal_currency = False
                continue
            auto = line._l10n_ve_automatic_company_subtotal()
            if line.company_currency_id.is_zero(auto):
                continue
            line.manually_price_subtotal_currency = bool(
                line.company_currency_id.compare_amounts(
                    line.price_subtotal_currency, auto
                )
            )

    def _inverse_price_total_currency(self):
        if self.env.context.get("l10n_ve_resetting_company_currency"):
            return
        for line in self:
            if (
                line.display_type != "product"
                or line.move_id.move_type not in INVOICE_MOVE_TYPES
            ):
                continue
            if line.company_currency_id.is_zero(line.price_total_currency):
                continue
            auto = line._l10n_ve_automatic_company_total()
            if line.company_currency_id.is_zero(auto):
                continue
            if not line.company_currency_id.compare_amounts(
                line.price_total_currency, auto
            ):
                if not line.manually_price_subtotal_currency:
                    continue
                line.manually_price_subtotal_currency = False
                line.price_subtotal_currency = (
                    line._l10n_ve_automatic_company_subtotal()
                )
                continue
            if line._l10n_ve_stale_company_total():
                reset = line.with_context(l10n_ve_resetting_company_currency=True)
                reset.manually_price_subtotal_currency = False
                reset.price_subtotal_currency = (
                    reset._l10n_ve_automatic_company_subtotal()
                )
                reset.price_total_currency = reset._l10n_ve_automatic_company_total()
                continue
            if not line.price_total:
                continue
            rate = abs(line.price_total) / abs(line.price_total_currency)
            line.manually_price_subtotal_currency = True
            line.price_subtotal_currency = line.company_currency_id.round(
                abs(line.price_subtotal) / rate
            )

    @api.depends(
        "price_unit",
        "quantity",
        "discount",
        "price_subtotal_currency",
        "currency_rate",
        "currency_id",
        "company_currency_id",
    )
    def _compute_price_unit_company_currency(self):
        prec = self.env["decimal.precision"].precision_get("Product Price")
        for line in self:
            if line.currency_id == line.company_currency_id:
                line.price_unit_company_currency = float_round(
                    line.price_unit or 0.0, precision_digits=prec
                )
                continue
            move = line.move_id
            rate = move.invoice_currency_rate or line.currency_rate or 0.0
            if (
                move
                and move.is_invoice(include_receipts=True)
                and rate
                and hasattr(move, "_l10n_ve_company_price_unit_from_foreign_unit")
            ):
                line.price_unit_company_currency = (
                    move._l10n_ve_company_price_unit_from_foreign_unit(
                        line.price_unit or 0.0, rate=rate
                    )
                )
                continue
            if not rate:
                line.price_unit_company_currency = float_round(
                    line.price_unit or 0.0, precision_digits=prec
                )
                continue
            line.price_unit_company_currency = float_round(
                (line.price_unit or 0.0) / rate, precision_digits=prec
            )

    @api.depends(
        "currency_id",
        "company_id",
        "move_id.invoice_currency_rate",
        "move_id.date",
        "price_subtotal",
        "price_subtotal_currency",
        "manually_price_subtotal_currency",
    )
    def _compute_currency_rate(self):
        res = super()._compute_currency_rate()
        for line in self.filtered(
            lambda aml: aml.manually_price_subtotal_currency
            and aml.price_subtotal_currency
        ):
            manual_rate = line._l10n_ve_manual_currency_rate()
            if not manual_rate:
                continue
            line.currency_rate = manual_rate
            if (
                line.display_type == "product"
                and line.move_id.state == "draft"
                and line.move_id.is_invoice(include_receipts=True)
                and line.amount_currency
            ):
                line.balance = line.company_currency_id.round(
                    line.amount_currency / manual_rate
                )
        for line in self.filtered(lambda aml: not aml.currency_rate):
            line.currency_rate = line.move_id.invoice_currency_rate or 1.0
        return res

    @contextmanager
    def _sync_invoice(self, container):
        with super()._sync_invoice(container):
            yield
            for line in container["records"].filtered(
                lambda aml: aml.move_id.is_invoice(include_receipts=True)
                and not aml.currency_rate
            ):
                line.currency_rate = line.move_id.invoice_currency_rate or 1.0

    @api.depends(
        "currency_rate",
        "move_id.invoice_currency_rate",
        "price_subtotal_currency",
        "manually_price_subtotal_currency",
        "price_subtotal",
    )
    def _compute_warning_rate_difference(self):
        for line in self:
            if not (
                line.manually_price_subtotal_currency
                and line.price_subtotal_currency
                and line.price_subtotal
            ):
                line.warning_rate_difference = False
                continue
            line.warning_rate_difference = bool(
                float_compare(
                    line._l10n_ve_manual_currency_rate(),
                    line.move_id.invoice_currency_rate or 1.0,
                    precision_digits=6,
                )
            )

    @api.depends("currency_rate", "move_id.invoice_currency_rate")
    def _compute_has_rate_difference(self):
        for line in self:
            line.has_rate_difference = line._l10n_ve_has_rate_difference()

    @api.onchange("price_unit", "quantity", "discount", "tax_ids")
    def _onchange_l10n_ve_company_currency_amount(self):
        for line in self.filtered(
            lambda aml: aml.display_type == "product"
            and aml.move_id.move_type in INVOICE_MOVE_TYPES
        ):
            line.manually_price_subtotal_currency = False
            line.price_subtotal_currency = line._l10n_ve_automatic_company_subtotal()
            line.price_total_currency = line._l10n_ve_automatic_company_total()

    @api.onchange("price_subtotal_currency")
    def _onchange_price_subtotal_currency(self):
        for line in self:
            if (
                line.display_type != "product"
                or line.move_id.move_type not in INVOICE_MOVE_TYPES
            ):
                continue
            auto = line._l10n_ve_automatic_company_subtotal()
            if line.company_currency_id.compare_amounts(
                line.price_subtotal_currency, auto
            ):
                line.manually_price_subtotal_currency = True
            else:
                line.manually_price_subtotal_currency = False
            line.price_total_currency = line._l10n_ve_automatic_company_total()

    @api.onchange("price_total_currency")
    def _onchange_price_total_currency(self):
        for line in self:
            if (
                line.display_type != "product"
                or line.move_id.move_type not in INVOICE_MOVE_TYPES
            ):
                continue
            auto = line._l10n_ve_automatic_company_total()
            if not line.company_currency_id.compare_amounts(
                line.price_total_currency, auto
            ):
                line.manually_price_subtotal_currency = False
                line.price_subtotal_currency = (
                    line._l10n_ve_automatic_company_subtotal()
                )
                continue
            if not line.price_total or not line.price_total_currency:
                continue
            rate = abs(line.price_total) / abs(line.price_total_currency)
            line.manually_price_subtotal_currency = True
            line.price_subtotal_currency = line.company_currency_id.round(
                abs(line.price_subtotal) / rate
            )

    def write(self, vals):
        vals = dict(vals)
        protect_keys = {"quantity", "price_unit", "discount", "tax_ids"}
        company_amount_keys = {"price_subtotal_currency", "price_total_currency"}
        protected = {}
        if protect_keys & set(vals) and not self.env.context.get(
            "l10n_ve_skip_manual_company_protect"
        ):
            # The form resends the previous company amounts together with the
            # new quantity. On a line that was not manual, those amounts are
            # leftovers, not a rate typed by the user.
            if not vals.get("manually_price_subtotal_currency"):
                automatic = self.filtered(
                    lambda line: line.id and not line.manually_price_subtotal_currency
                )
                if automatic and company_amount_keys & set(vals):
                    if automatic != self:
                        clean = {
                            key: value
                            for key, value in vals.items()
                            if key not in company_amount_keys
                        }
                        clean["manually_price_subtotal_currency"] = False
                        return automatic.write(clean) and (self - automatic).write(
                            vals
                        )
                    for key in company_amount_keys:
                        vals.pop(key, None)
                    vals["manually_price_subtotal_currency"] = False
            protected = {
                line.id: line.price_subtotal_currency
                for line in self
                if line.id and line.manually_price_subtotal_currency
            }
        res = super().write(vals)
        if protected:
            for line in self.filtered(
                lambda aml: aml.id in protected and aml.manually_price_subtotal_currency
            ):
                if line.company_currency_id.compare_amounts(
                    line.price_subtotal_currency, protected[line.id]
                ):
                    line.with_context(l10n_ve_skip_manual_company_protect=True).write(
                        {
                            "price_subtotal_currency": protected[line.id],
                            "manually_price_subtotal_currency": True,
                        }
                    )
        return res

    def reset_price_subtotal_currency(self):
        self.manually_price_subtotal_currency = False
        for line in self:
            line.price_subtotal_currency = line._l10n_ve_automatic_company_subtotal()
            line.price_total_currency = line._l10n_ve_automatic_company_total()

    def _l10n_ve_has_rate_difference(self):
        self.ensure_one()
        if not self.move_id.is_invoice(include_receipts=True):
            return False
        return bool(
            float_compare(
                self.currency_rate or 0.0,
                self.move_id.invoice_currency_rate or 0.0,
                precision_digits=6,
            )
        )

    def _l10n_ve_manual_currency_rate(self):
        self.ensure_one()
        if not self.price_subtotal_currency or not self.price_subtotal:
            return 0.0
        return abs(self.price_subtotal) / abs(self.price_subtotal_currency)

    def _l10n_ve_draft_refund_company_subtotal(self):
        """Company subtotal of a draft credit note scaled from the origin line.

        ``balance`` still holds the full origin amount while the form edits the
        quantity, so the display cannot follow it.
        """
        self.ensure_one()
        move = self.move_id
        if (
            move.state != "draft"
            or move.move_type not in ("out_refund", "in_refund")
            or not move.reversed_entry_id
            or move.currency_id == move.company_currency_id
            or self.display_type != "product"
        ):
            return None
        origin = move._l10n_ve_find_origin_product_line_for_refund(self)
        if not origin:
            return None
        if hasattr(move, "_l10n_ve_refund_line_target_company_subtotal"):
            return abs(
                move._l10n_ve_refund_line_target_company_subtotal(origin, self)
            )
        company = self.company_currency_id
        origin_subtotal = abs(origin.balance or 0.0)
        if company.is_zero(origin_subtotal):
            origin_subtotal = abs(origin.price_subtotal_currency or 0.0)
        if not origin.quantity:
            return company.round(origin_subtotal)
        qty_ratio = (self.quantity or 0.0) / origin.quantity
        price_ratio = (
            (self.price_unit or 0.0) / origin.price_unit if origin.price_unit else 1.0
        )
        origin_discount = 1.0 - (origin.discount or 0.0) / 100.0
        credit_discount = 1.0 - (self.discount or 0.0) / 100.0
        discount_ratio = credit_discount / origin_discount if origin_discount else 0.0
        return company.round(origin_subtotal * qty_ratio * price_ratio * discount_ratio)

    def _l10n_ve_automatic_company_subtotal(self):
        self.ensure_one()
        refund_subtotal = self._l10n_ve_draft_refund_company_subtotal()
        if refund_subtotal is not None:
            return refund_subtotal
        return self._l10n_ve_company_currency_subtotal()

    def _l10n_ve_automatic_company_total(self):
        self.ensure_one()
        return self._l10n_ve_company_currency_total_from_company_base(
            self._l10n_ve_automatic_company_subtotal()
        )

    def _l10n_ve_stale_company_total(self):
        """Company total still equals the origin while the foreign subtotal changed."""
        self.ensure_one()
        origin = self._origin
        if not origin or not origin.id:
            return False
        company = self.company_currency_id
        origin_total = origin.price_total_currency or 0.0
        if company.is_zero(origin_total):
            return False
        if company.compare_amounts(self.price_total_currency or 0.0, origin_total):
            return False
        return bool(
            self.currency_id.compare_amounts(
                self.price_subtotal or 0.0, origin.price_subtotal or 0.0
            )
        )

    def _l10n_ve_company_currency_subtotal(self):
        self.ensure_one()
        if (
            self.move_id.move_type not in INVOICE_MOVE_TYPES
            or self.display_type != "product"
        ):
            return 0.0
        if self.currency_id == self.company_currency_id:
            return self.company_currency_id.round(
                (self.price_unit or 0.0)
                * (self.quantity or 0.0)
                * (1.0 - (self.discount or 0.0) / 100.0)
            )
        move = self.move_id
        rate = move.invoice_currency_rate or self.currency_rate or 0.0
        if not rate:
            return 0.0
        if hasattr(move, "_l10n_ve_company_line_subtotal_from_foreign_unit"):
            return move._l10n_ve_company_line_subtotal_from_foreign_unit(
                self.price_unit or 0.0,
                self.quantity or 0.0,
                discount=self.discount or 0.0,
                rate=rate,
            )
        foreign_subtotal = self.currency_id.round(
            (self.price_unit or 0.0)
            * (self.quantity or 0.0)
            * (1.0 - (self.discount or 0.0) / 100.0)
        )
        return self.company_currency_id.round(foreign_subtotal / rate)

    def _l10n_ve_company_currency_total_from_foreign_total(self):
        self.ensure_one()
        foreign_total = self.price_total or 0.0
        if self.currency_id == self.company_currency_id:
            return self.company_currency_id.round(foreign_total)
        rate = self.move_id.invoice_currency_rate or 0.0
        if not rate:
            return 0.0
        return self.company_currency_id.round(foreign_total / rate)

    def _l10n_ve_company_currency_total_from_company_base(self, subtotal_company):
        self.ensure_one()
        company_currency = self.company_currency_id
        if self.currency_id == company_currency:
            return company_currency.round(self.price_total or 0.0)
        taxes = self.tax_ids.flatten_taxes_hierarchy()
        if not taxes:
            return company_currency.round(subtotal_company)
        if any(tax.amount_type != "percent" for tax in taxes):
            return self._l10n_ve_company_currency_total_from_foreign_total()
        total = subtotal_company
        for tax in taxes:
            total += company_currency.round(subtotal_company * tax.amount / 100.0)
        return company_currency.round(total)

    def _l10n_ve_company_currency_total_at_invoice_rate(self):
        self.ensure_one()
        if (
            self.move_id.move_type not in INVOICE_MOVE_TYPES
            or self.display_type != "product"
        ):
            return 0.0
        return self._l10n_ve_company_currency_total_from_company_base(
            self._l10n_ve_company_currency_subtotal()
        )

    def _l10n_ve_company_currency_total(self):
        self.ensure_one()
        if (
            self.move_id.move_type not in INVOICE_MOVE_TYPES
            or self.display_type != "product"
        ):
            return 0.0
        if (
            self.manually_price_subtotal_currency
            and self.price_subtotal
            and self.price_subtotal_currency
        ):
            return self.company_currency_id.round(
                (self.price_total or 0.0)
                * self.price_subtotal_currency
                / self.price_subtotal
            )
        return self._l10n_ve_company_currency_total_from_company_base(
            self.price_subtotal_currency
        )
