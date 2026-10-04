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
    price_unit_company_currency = fields.Monetary(
        compute="_compute_price_unit_company_currency",
        currency_field="company_currency_id",
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

    @api.depends("balance", "move_id.move_type", "manually_price_subtotal_currency")
    def _compute_price_subtotal_currency(self):
        for line in self:
            if line.manually_price_subtotal_currency:
                continue
            line.price_subtotal_currency = line._l10n_ve_company_currency_subtotal()

    @api.depends("price_subtotal_currency", "discount", "quantity")
    def _compute_price_unit_company_currency(self):
        for line in self:
            qty = line.quantity or 0.0
            if not qty:
                line.price_unit_company_currency = 0.0
                continue
            discount_factor = 1 - ((line.discount or 0.0) / 100.0)
            if not discount_factor:
                line.price_unit_company_currency = 0.0
                continue
            subtotal_wo_discount = line.price_subtotal_currency / discount_factor
            line.price_unit_company_currency = subtotal_wo_discount / qty

    @api.depends(
        "price_subtotal_currency",
        "manually_price_subtotal_currency",
        "amount_currency",
    )
    def _compute_currency_rate(self):
        res = super()._compute_currency_rate()
        for line in self.filtered(
            lambda aml: aml.manually_price_subtotal_currency
            and aml.price_subtotal_currency
        ):
            line.currency_rate = line._l10n_ve_manual_currency_rate()
        return res

    @api.depends(
        "currency_rate",
        "move_id.invoice_currency_rate",
        "price_subtotal_currency",
        "manually_price_subtotal_currency",
        "amount_currency",
    )
    def _compute_warning_rate_difference(self):
        for line in self:
            if not (
                line.manually_price_subtotal_currency and line.price_subtotal_currency
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
            line.price_subtotal_currency = (
                line._l10n_ve_company_currency_subtotal_from_price()
            )

    @api.onchange("price_subtotal_currency")
    def _onchange_price_subtotal_currency(self):
        for line in self.filtered("price_subtotal_currency"):
            if line.company_currency_id.compare_amounts(
                line.price_subtotal_currency,
                line._l10n_ve_company_currency_subtotal_from_price(),
            ):
                line.manually_price_subtotal_currency = True

    def reset_price_subtotal_currency(self):
        self.manually_price_subtotal_currency = False

    def _l10n_ve_company_currency_subtotal(self):
        self.ensure_one()
        if self.move_id.move_type not in INVOICE_MOVE_TYPES:
            return 0.0
        if isinstance(self.id, models.NewId) and self.display_type == "product":
            return self._l10n_ve_company_currency_subtotal_from_price()
        return abs(self.balance)

    def _l10n_ve_company_currency_subtotal_from_price(self):
        self.ensure_one()
        rate = self.move_id.invoice_currency_rate or 1.0
        return self.company_currency_id.round(abs(self.price_subtotal) / rate)

    def _l10n_ve_manual_currency_rate(self):
        self.ensure_one()
        return abs(self.amount_currency) / abs(self.price_subtotal_currency)
