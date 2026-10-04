# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_compare, float_round


class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_currency_rate = fields.Float(recursive=True)
    l10n_ve_inverse_rate = fields.Float(
        string="Tasa de Cambio Inversa",
        compute="_compute_l10n_ve_inverse_rate",
        store=True,
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
            if move.country_code != "VE" or not move.tax_totals:
                continue
            totals = dict(move.tax_totals)
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
        vals = self._l10n_ve_drop_invalid_invoice_currency_rate_from_vals(vals)
        res = super().write(vals)
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

    def _get_product_base_line_currency_rate(self, product_line):
        if (
            self.is_invoice(include_receipts=True)
            and product_line.manually_price_subtotal_currency
            and product_line.price_subtotal_currency
        ):
            return product_line.currency_rate
        return super()._get_product_base_line_currency_rate(product_line)

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
        if not qty:
            return line.price_unit_company_currency
        discount_factor = 1.0 - (line.discount or 0.0) / 100.0
        if discount_factor <= 0.0:
            return 0.0
        subtotal = self._l10n_ve_company_subtotal_unrounded_from_origin_line(line)
        prec = self.env["decimal.precision"].precision_get("Product Price")
        return float_round(subtotal / discount_factor / qty, precision_digits=prec)

    def _l10n_ve_company_subtotal_from_origin_line(self, line):
        if line.currency_id == line.company_currency_id:
            return abs(line.price_subtotal)
        return line.price_subtotal_currency

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
