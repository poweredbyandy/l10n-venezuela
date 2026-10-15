# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_compare

INVOICE_MOVE_TYPES = ("out_invoice", "in_invoice", "out_refund", "in_refund")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    price_subtotal_currency = fields.Monetary(
        string="Subtotal in Company Currency",
        compute="_compute_price_subtotal_currency",
        currency_field="company_currency_id",
        store=True,
        precompute=True,
        readonly=False,
    )
    # Float (not Monetary): keep full precision so unit × qty equals the
    # company subtotal; Monetary would round the unit to currency decimals
    # and break that identity for fractional unit prices.
    price_unit_company_currency = fields.Float(
        string="Unit Price in Company Currency",
        compute="_compute_price_unit_company_currency",
        digits=(16, 6),
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
        "move_id.move_type",
        "move_id.invoice_currency_rate",
        "manually_price_subtotal_currency",
    )
    def _compute_price_subtotal_currency(self):
        for line in self:
            if line.manually_price_subtotal_currency:
                continue
            line.price_subtotal_currency = line._l10n_ve_company_currency_subtotal()

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
        """Company unit price aligned with the displayed company subtotal.

        Derive from ``price_subtotal_currency / (qty * (1 - discount%))`` so
        unit × quantity matches the line company subtotal clients verify by
        hand, instead of converting the unrounded foreign ``price_unit``.
        """
        for line in self:
            if line.currency_id == line.company_currency_id or not line.currency_rate:
                line.price_unit_company_currency = line.price_unit
                continue
            qty = line.quantity or 0.0
            discount_factor = 1.0 - ((line.discount or 0.0) / 100.0)
            base_qty = qty * discount_factor
            if base_qty and line.price_subtotal_currency:
                line.price_unit_company_currency = (
                    line.price_subtotal_currency / base_qty
                )
                continue
            line.price_unit_company_currency = line.price_unit / line.currency_rate

    @api.depends(
        "price_subtotal_currency",
        "manually_price_subtotal_currency",
        "price_subtotal",
    )
    def _compute_currency_rate(self):
        res = super()._compute_currency_rate()
        for line in self.filtered(
            lambda aml: aml.manually_price_subtotal_currency
            and aml.price_subtotal_currency
        ):
            manual_rate = line._l10n_ve_manual_currency_rate()
            if manual_rate:
                line.currency_rate = manual_rate
        return res

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
            line.has_rate_difference = (
                line.currency_rate != line.move_id.invoice_currency_rate
            )

    @api.onchange("price_unit", "quantity", "discount", "tax_ids")
    def _onchange_l10n_ve_company_currency_amount(self):
        for line in self.filtered(
            lambda aml: not aml.manually_price_subtotal_currency
            and aml.display_type == "product"
            and aml.move_id.move_type in INVOICE_MOVE_TYPES
        ):
            line.price_subtotal_currency = line._l10n_ve_company_currency_subtotal()

    @api.onchange("price_subtotal_currency")
    def _onchange_price_subtotal_currency(self):
        for line in self.filtered("price_subtotal_currency"):
            if line.company_currency_id.compare_amounts(
                line.price_subtotal_currency,
                line._l10n_ve_company_currency_subtotal(),
            ):
                line.manually_price_subtotal_currency = True

    def reset_price_subtotal_currency(self):
        self.manually_price_subtotal_currency = False

    def _l10n_ve_company_currency_subtotal(self):
        """Company-currency subtotal from the rounded foreign amount / rate.

        Keeps ``price_subtotal_currency`` aligned with the foreign
        ``price_subtotal`` customers see, instead of converting the unrounded
        ``price_unit * quantity`` residual.
        """
        self.ensure_one()
        if (
            self.move_id.move_type not in INVOICE_MOVE_TYPES
            or self.display_type != "product"
        ):
            return 0.0
        base_line = self.move_id._prepare_product_base_line_for_taxes_computation(self)
        self.env["account.tax"]._add_tax_details_in_base_line(
            base_line, self.company_id
        )
        return self.company_currency_id.round(
            base_line["tax_details"]["raw_total_excluded"]
        )

    def _l10n_ve_manual_currency_rate(self):
        self.ensure_one()
        return abs(self.price_subtotal) / abs(self.price_subtotal_currency)
