# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_compare, float_round


class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_currency_rate = fields.Float(recursive=True)
    l10n_ve_inverse_rate = fields.Float(
        string="Tasa de Cambio Inversa",
        compute="_compute_l10n_ve_inverse_rate",
        inverse="_inverse_l10n_ve_inverse_rate",
        store=True,
        readonly=False,
        help=(
            "Tasa de cambio inversa (inverse_rate) de la moneda de la factura "
            "para la fecha de la factura"
        ),
    )
    l10n_ve_currency_rate_outdated = fields.Boolean(
        string="Tasa de cambio desactualizada",
        compute="_compute_l10n_ve_currency_rate_outdated",
    )
    lines_with_rate_difference = fields.Boolean(
        string="Lines with exchange rate difference",
        compute="_compute_lines_with_rate_difference",
    )

    @api.depends(
        "state",
        "move_type",
        "currency_id",
        "company_currency_id",
        "invoice_currency_rate",
        "expected_currency_rate",
        "invoice_date",
        "country_code",
        "reversed_entry_id",
        "reversed_entry_id.invoice_currency_rate",
        "reversed_entry_id.currency_id",
    )
    def _compute_l10n_ve_currency_rate_outdated(self):
        for move in self:
            if (
                move.state != "draft"
                or move.move_type == "entry"
                or not move.currency_id
                or move.currency_id == move.company_currency_id
            ):
                move.l10n_ve_currency_rate_outdated = False
                continue
            if move._l10n_ve_refund_keeps_origin_currency_rate():
                move.l10n_ve_currency_rate_outdated = bool(
                    float_compare(
                        move.invoice_currency_rate,
                        move.reversed_entry_id.invoice_currency_rate,
                        precision_digits=6,
                    )
                )
                continue
            move.l10n_ve_currency_rate_outdated = bool(
                float_compare(
                    move.invoice_currency_rate,
                    move.expected_currency_rate,
                    precision_digits=6,
                )
            )

    @api.depends(
        "currency_id",
        "company_currency_id",
        "company_id",
        "invoice_date",
        "move_type",
        "reversed_entry_id",
        "reversed_entry_id.invoice_currency_rate",
        "reversed_entry_id.currency_id",
    )
    def _compute_invoice_currency_rate(self):
        res = super()._compute_invoice_currency_rate()
        for move in self:
            origin = move.reversed_entry_id
            if (
                move.move_type == "out_refund"
                and origin
                and move.currency_id
                and move.currency_id != move.company_currency_id
                and origin.currency_id == move.currency_id
                and origin.invoice_currency_rate
            ):
                move.invoice_currency_rate = origin.invoice_currency_rate
                continue
            if (
                not move.is_invoice(include_receipts=True)
                or not move.currency_id
                or move.currency_id == move.company_currency_id
                or move.invoice_currency_rate > 0
            ):
                continue
            rate = move._get_expected_currency_rate_at(
                move._get_invoice_currency_rate_date()
            )
            if rate > 0:
                move.invoice_currency_rate = rate
        return res

    @api.depends(
        "currency_id",
        "company_id",
        "company_currency_id",
        "invoice_currency_rate",
    )
    def _compute_l10n_ve_inverse_rate(self):
        for move in self:
            if not move.currency_id or not move.company_id:
                move.l10n_ve_inverse_rate = 0.0
                continue
            if move.currency_id == move.company_currency_id:
                move.l10n_ve_inverse_rate = 1.0
                continue
            rate = move.invoice_currency_rate or 0.0
            move.l10n_ve_inverse_rate = (1.0 / rate) if rate else 0.0

    def _inverse_l10n_ve_inverse_rate(self):
        # The document rate is applied in write(), after the invoice line
        # sync. Doing it here is overwritten when that sync restores the
        # previous rate.
        return

    def _l10n_ve_apply_inverse_rate(self):
        for move in self:
            if (
                not move.currency_id
                or not move.company_currency_id
                or move.currency_id == move.company_currency_id
            ):
                continue
            inverse = move.l10n_ve_inverse_rate or 0.0
            if not inverse:
                continue
            rate = 1.0 / inverse
            if not float_compare(move.invoice_currency_rate, rate, precision_digits=12):
                continue
            move.invoice_currency_rate = rate

    @api.depends("line_ids.has_rate_difference")
    def _compute_lines_with_rate_difference(self):
        for move in self:
            move.lines_with_rate_difference = any(
                move.invoice_line_ids.mapped("has_rate_difference")
            )

    @api.depends_context("lang")
    @api.depends(
        "invoice_line_ids.currency_rate",
        "invoice_line_ids.tax_base_amount",
        "invoice_line_ids.tax_line_id",
        "invoice_line_ids.price_total",
        "invoice_line_ids.price_subtotal",
        "invoice_payment_term_id",
        "partner_id",
        "currency_id",
        "invoice_line_ids.product_id",
    )
    def _compute_tax_totals(self):
        res = super()._compute_tax_totals()
        for move in self:
            if not move.tax_totals:
                continue
            totals = dict(move.tax_totals)
            if move.country_code == "VE":
                totals["same_tax_base"] = False
                company_currency = move.company_currency_id
                totals["display_in_company_currency"] = bool(
                    move.currency_id
                    and company_currency
                    and move.currency_id != company_currency
                )
                if company_currency and not totals.get("company_currency_id"):
                    totals["company_currency_id"] = company_currency.id
                for subtotal in totals.get("subtotals", []):
                    for tax_group in subtotal.get("tax_groups", []):
                        if tax_group.get("display_base_amount_currency") is False:
                            tax_group["display_base_amount_currency"] = tax_group.get(
                                "base_amount_currency", 0.0
                            )
                        if tax_group.get("display_base_amount") in (False, None):
                            tax_group["display_base_amount"] = tax_group.get(
                                "base_amount", 0.0
                            )
                move.tax_totals = totals
        return res

    @api.constrains("invoice_currency_rate")
    def _check_invoice_currency_rate(self):
        moves = self.filtered(lambda move: move.state != "draft")
        if moves:
            return super(AccountMove, moves)._check_invoice_currency_rate()

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [
            self._l10n_ve_drop_invalid_invoice_currency_rate_from_vals(dict(vals))
            for vals in vals_list
        ]
        records = super().create(vals_list)
        records._l10n_ve_ensure_draft_invoice_currency_rate()
        records._l10n_ve_lock_refund_rate_if_needed()
        return records

    def write(self, vals):
        inverse_edit = "l10n_ve_inverse_rate" in vals
        vals = self._l10n_ve_drop_invalid_invoice_currency_rate_from_vals(vals)
        res = super().write(vals)
        if inverse_edit:
            self._l10n_ve_apply_inverse_rate()
        self._l10n_ve_ensure_draft_invoice_currency_rate()
        if not self.env.context.get("l10n_ve_skip_refund_rate_lock") and {
            "invoice_date",
            "date",
            "currency_id",
            "reversed_entry_id",
        } & set(vals):
            self._l10n_ve_lock_refund_rate_if_needed()
        return res

    def refresh_invoice_currency_rate(self):
        refunds = self._l10n_ve_refunds_keeping_origin_rate()
        others = self - refunds
        res = None
        if others:
            res = super(AccountMove, others).refresh_invoice_currency_rate()
        refunds._l10n_ve_lock_refund_invoice_currency_rate_from_origin()
        return res

    @api.model
    def _l10n_ve_drop_invalid_invoice_currency_rate_from_vals(self, vals):
        if vals.get("invoice_currency_rate", 1) > 0:
            return vals
        if "invoice_currency_rate" not in vals:
            return vals
        if not self or all(move.state == "draft" for move in self):
            vals = dict(vals)
            vals.pop("invoice_currency_rate", None)
        return vals

    def _l10n_ve_ensure_draft_invoice_currency_rate(self):
        moves = self.filtered(
            lambda move: move.state == "draft"
            and move.is_invoice(include_receipts=True)
            and move.currency_id
            and move.company_id
            and move.currency_id != move.company_currency_id
            and move.invoice_currency_rate <= 0
        )
        for move in moves:
            rate = move._get_expected_currency_rate_at(
                move._get_invoice_currency_rate_date()
            )
            if rate > 0:
                move.invoice_currency_rate = rate

    def _l10n_ve_refunds_keeping_origin_rate(self):
        return self.filtered(
            lambda move: move.move_type == "out_refund"
            and move.reversed_entry_id
            and move.currency_id != move.company_currency_id
            and move.reversed_entry_id.currency_id == move.currency_id
        )

    def _l10n_ve_lock_refund_rate_if_needed(self):
        self._l10n_ve_refunds_keeping_origin_rate()._l10n_ve_lock_refund_invoice_currency_rate_from_origin()

    def _l10n_ve_refund_keeps_origin_currency_rate(self):
        """Credit notes keep the origin invoice rate even on a later date."""
        self.ensure_one()
        origin = self.reversed_entry_id
        return bool(
            self.move_type == "out_refund"
            and self.country_code == "VE"
            and origin
            and self.currency_id
            and self.currency_id != self.company_currency_id
            and origin.currency_id == self.currency_id
            and origin.invoice_currency_rate
        )

    def _l10n_ve_lock_refund_invoice_currency_rate_from_origin(self):
        for move in self:
            origin = move.reversed_entry_id
            if (
                move.move_type != "out_refund"
                or not origin
                or move.currency_id == move.company_currency_id
                or origin.currency_id != move.currency_id
                or not origin.invoice_currency_rate
            ):
                continue
            origin_rate = origin.invoice_currency_rate
            if not float_compare(
                move.invoice_currency_rate,
                origin_rate,
                precision_digits=6,
            ):
                continue
            with move.env.protecting([move._fields["invoice_currency_rate"]], move):
                move.with_context(
                    check_move_validity=False,
                    l10n_ve_skip_refund_rate_lock=True,
                ).write({"invoice_currency_rate": origin_rate})
            move.invalidate_recordset(["l10n_ve_inverse_rate"])

    def _l10n_ve_to_company_abs_amount(self):
        self.ensure_one()
        if (
            self.move_type == "out_refund"
            and self.reversed_entry_id
            and self.currency_id != self.company_currency_id
            and self.country_code == "VE"
        ):
            return self._l10n_ve_refund_company_abs_amount_from_origin()
        lines = self.line_ids.filtered(
            lambda line: line.display_type
            in ("product", "tax", "rounding", "global_discount", "discount")
        )
        if lines:
            return abs(sum(lines.mapped("balance")))
        rp_lines = self.line_ids.filtered(
            lambda line: line.account_id.account_type
            in ("asset_receivable", "liability_payable")
        )
        if rp_lines:
            return abs(sum(rp_lines.mapped("balance")))
        return abs(self.amount_total_signed)

    def _l10n_ve_refund_company_abs_amount_from_origin(self):
        self.ensure_one()
        origin = self.reversed_entry_id
        company_cur = self.company_currency_id
        origin_total = abs(origin.amount_total)
        origin_company = origin._l10n_ve_to_company_abs_amount()
        if (
            self.currency_id == origin.currency_id
            and not self.currency_id.is_zero(origin_total)
            and not company_cur.is_zero(origin_company)
        ):
            ratio = abs(self.amount_total) / origin_total
            return company_cur.round(origin_company * ratio)
        origin_date = (
            origin.invoice_date or origin.date or fields.Date.context_today(self)
        )
        return company_cur.round(
            self.currency_id._convert(
                abs(self.amount_total),
                company_cur,
                self.company_id,
                origin_date,
            )
        )

    def _l10n_ve_to_company_abs_untaxed_amount(self):
        self.ensure_one()
        lines = self.line_ids.filtered(
            lambda line: line.display_type in ("product", "global_discount", "discount")
            or (line.display_type == "rounding" and not line.tax_repartition_line_id)
        )
        if lines:
            return abs(sum(lines.mapped("balance")))
        return abs(self.amount_untaxed_signed)

    def _l10n_ve_document_base_amount(self, line):
        qty = abs(line.quantity or 0.0)
        discount_factor = 1.0 - (line.discount or 0.0) / 100.0
        return qty * (line.price_unit or 0.0) * discount_factor

    def _l10n_ve_company_subtotal_unrounded_from_origin_line(self, line):
        raw_base = self._l10n_ve_document_base_amount(line)
        if line.currency_id == line.company_currency_id:
            return raw_base
        date = (
            line.move_id.invoice_date
            or line.move_id.date
            or fields.Date.context_today(self)
        )
        return line.currency_id._convert(
            raw_base,
            line.company_currency_id,
            line.company_id,
            date,
            round=False,
        )

    def _l10n_ve_company_price_unit_from_origin_line(self, line):
        if line.currency_id == line.company_currency_id:
            return line.price_unit
        qty = abs(line.quantity or 0.0)
        discount_factor = 1.0 - (line.discount or 0.0) / 100.0
        prec = self.env["decimal.precision"].precision_get("Product Price")
        if qty and discount_factor > 0.0 and line.balance:
            return float_round(
                abs(line.balance) / qty / discount_factor, precision_digits=prec
            )
        if line.price_unit_company_currency:
            return line.price_unit_company_currency
        if not qty:
            return line.price_unit_company_currency or 0.0
        if discount_factor <= 0.0:
            return 0.0
        subtotal = self._l10n_ve_company_subtotal_unrounded_from_origin_line(line)
        return float_round(subtotal / discount_factor / qty, precision_digits=prec)

    def _l10n_ve_find_origin_product_line_for_refund(self, credit_line):
        self.ensure_one()
        origin = self.reversed_entry_id
        if not origin:
            return self.env["account.move.line"]
        origin_products = origin.invoice_line_ids.filtered(
            lambda origin_line: origin_line.display_type == "product"
        )
        price_prec = self.env["decimal.precision"].precision_get("Product Price")
        qty_prec = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )

        def _same_price(origin_line):
            return not float_compare(
                origin_line.price_unit or 0.0,
                credit_line.price_unit or 0.0,
                precision_digits=price_prec,
            )

        def _same_qty(origin_line):
            return not float_compare(
                abs(origin_line.quantity or 0.0),
                abs(credit_line.quantity or 0.0),
                precision_digits=qty_prec,
            )

        def _same_taxes(origin_line):
            return tuple(sorted(origin_line.tax_ids.ids)) == tuple(
                sorted(credit_line.tax_ids.ids)
            )

        candidates = origin_products.filtered(
            lambda origin_line: _same_taxes(origin_line)
            and _same_price(origin_line)
            and _same_qty(origin_line)
        )
        if len(candidates) == 1:
            return candidates
        if len(candidates) > 1:
            same_name = candidates.filtered(
                lambda origin_line: (origin_line.name or "") == (credit_line.name or "")
            )
            if len(same_name) == 1:
                return same_name
            same_seq = candidates.filtered(
                lambda origin_line: origin_line.sequence == credit_line.sequence
            )
            return same_seq[:1] or same_name[:1] or candidates[:1]
        candidates = origin_products.filtered(
            lambda origin_line: _same_taxes(origin_line) and _same_price(origin_line)
        )
        if len(candidates) == 1:
            return candidates
        if candidates:
            same_seq = candidates.filtered(
                lambda origin_line: origin_line.sequence == credit_line.sequence
            )
            return same_seq[:1] or candidates[:1]
        return self.env["account.move.line"]

    def _l10n_ve_company_subtotal_from_origin_line(self, line):
        if line.currency_id == line.company_currency_id:
            return abs(line.price_subtotal)
        return abs(line.balance)

    def _l10n_ve_company_price_unit_from_refund_line(self, origin_line, credit_line):
        origin_pu = self._l10n_ve_company_price_unit_from_origin_line(origin_line)
        origin_currency = origin_line.currency_id
        if origin_currency.is_zero(origin_line.price_unit):
            return origin_pu
        if credit_line.currency_id != origin_currency:
            return origin_pu
        if not float_compare(
            origin_line.price_unit,
            credit_line.price_unit,
            precision_rounding=origin_currency.rounding,
        ):
            return origin_pu
        return origin_pu * (credit_line.price_unit / origin_line.price_unit)

    def _l10n_ve_company_price_unit_from_foreign_unit(self, price_unit, rate=None):
        """Round foreign unit price to company currency like a native Bs document.

        ``pu_bs = round(pu_usd / invoice_currency_rate, Product Price)`` so the
        same list-price unit converted at the invoice rate matches a VES invoice.
        """
        self.ensure_one()
        if self.currency_id == self.company_currency_id:
            return price_unit or 0.0
        rate = rate if rate is not None else (self.invoice_currency_rate or 0.0)
        if not rate:
            return 0.0
        prec = self.env["decimal.precision"].precision_get("Product Price")
        return float_round((price_unit or 0.0) / rate, precision_digits=prec)

    def _l10n_ve_company_line_subtotal_from_foreign_unit(
        self, price_unit, quantity, discount=0.0, rate=None
    ):
        """Company subtotal from rounded company unit price (native Bs math)."""
        self.ensure_one()
        company_pu = self._l10n_ve_company_price_unit_from_foreign_unit(
            price_unit, rate=rate
        )
        discount_factor = 1.0 - ((discount or 0.0) / 100.0)
        return self.company_currency_id.round(
            company_pu * (quantity or 0.0) * discount_factor
        )

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        base_line = super()._prepare_product_base_line_for_taxes_computation(
            product_line
        )
        self._l10n_ve_apply_rounded_foreign_price_unit(product_line, base_line)
        if (
            self.is_invoice(include_receipts=True)
            and self.currency_id != self.company_currency_id
            and product_line.display_type in ("product", "cogs")
            and not self.env.context.get("l10n_ve_unrounded_tax_base")
        ):
            company_pu = None
            if self.move_type in ("out_refund", "in_refund") and self.reversed_entry_id:
                origin_line = self._l10n_ve_find_origin_product_line_for_refund(
                    product_line
                )
                if origin_line:
                    company_pu = self._l10n_ve_company_price_unit_from_refund_line(
                        origin_line, product_line
                    )
                    origin_subtotal = abs(origin_line.balance or 0.0)
                    if origin_line.quantity:
                        company_total = self.company_currency_id.round(
                            origin_subtotal
                            * ((product_line.quantity or 0.0) / origin_line.quantity)
                        )
                    else:
                        company_total = self.company_currency_id.round(origin_subtotal)
                    base_line["l10n_ve_company_total_excluded"] = company_total
            if company_pu is None:
                company_pu = self._l10n_ve_company_price_unit_from_foreign_unit(
                    product_line.price_unit or 0.0
                )
            base_line["l10n_ve_company_price_unit"] = company_pu
        return base_line

    def _l10n_ve_apply_rounded_foreign_price_unit(self, product_line, base_line):
        """Keep foreign (USD) subtotal currency-rounded for document amounts.

        Company (Bs) amounts use ``l10n_ve_company_price_unit`` instead of
        dividing the foreign subtotal by the rate.
        """
        if self.env.context.get("l10n_ve_unrounded_tax_base"):
            return
        if not self.is_invoice(include_receipts=True):
            return
        if self.currency_id == self.company_currency_id:
            return
        if product_line.display_type not in ("product", "cogs"):
            return
        currency = base_line.get("currency_id") or self.currency_id
        quantity = base_line.get("quantity") or 0.0
        discount_factor = 1.0 - ((base_line.get("discount") or 0.0) / 100.0)
        if not quantity or discount_factor <= 0.0:
            return
        foreign_subtotal = currency.round(
            (product_line.price_unit or 0.0) * quantity * discount_factor
        )
        base_line["price_unit"] = foreign_subtotal / quantity / discount_factor
