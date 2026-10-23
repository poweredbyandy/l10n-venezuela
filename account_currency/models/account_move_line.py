# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.tools import float_compare, float_round

INVOICE_MOVE_TYPES = ("out_invoice", "in_invoice", "out_refund", "in_refund")


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    price_subtotal_currency = fields.Monetary(
        string="Subtotal in Company Currency",
        compute="_compute_price_subtotal_currency",
        currency_field="company_currency_id",
        store=True,
        precompute=True,
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
        "move_id.move_type",
        "move_id.invoice_currency_rate",
    )
    def _compute_price_subtotal_currency(self):
        for line in self:
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
        prec = self.env["decimal.precision"].precision_get("Product Price")
        for line in self:
            if line.currency_id == line.company_currency_id or not line.currency_rate:
                line.price_unit_company_currency = float_round(
                    line.price_unit or 0.0, precision_digits=prec
                )
                continue
            qty = line.quantity or 0.0
            discount_factor = 1.0 - ((line.discount or 0.0) / 100.0)
            base_qty = qty * discount_factor
            if base_qty and line.price_subtotal_currency:
                line.price_unit_company_currency = float_round(
                    line.price_subtotal_currency / base_qty, precision_digits=prec
                )
                continue
            line.price_unit_company_currency = float_round(
                (line.price_unit or 0.0) / line.currency_rate, precision_digits=prec
            )

    @api.depends("currency_rate", "move_id.invoice_currency_rate")
    def _compute_warning_rate_difference(self):
        for line in self:
            line.warning_rate_difference = line._l10n_ve_has_rate_difference()

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
            line.price_subtotal_currency = line._l10n_ve_company_currency_subtotal()

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

    def _l10n_ve_company_currency_subtotal(self):
        self.ensure_one()
        if (
            self.move_id.move_type not in INVOICE_MOVE_TYPES
            or self.display_type != "product"
        ):
            return 0.0
        foreign_subtotal = self.currency_id.round(
            (self.price_unit or 0.0)
            * (self.quantity or 0.0)
            * (1.0 - (self.discount or 0.0) / 100.0)
        )
        if self.currency_id == self.company_currency_id:
            return self.company_currency_id.round(foreign_subtotal)
        rate = self.move_id.invoice_currency_rate or self.currency_rate or 0.0
        if not rate:
            return 0.0
        return self.company_currency_id.round(foreign_subtotal / rate)
