# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, frozendict


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    display_type = fields.Selection(
        selection_add=[("global_discount", "Global Discount")],
        ondelete={"global_discount": "cascade"},
    )

    l10n_ve_global_discount_line = fields.Boolean(
        string="Venezuela global discount line",
        readonly=True,
        copy=False,
    )
    l10n_ve_line_discount_line = fields.Boolean(
        string="Venezuela line discount line",
        readonly=True,
        copy=False,
    )
    l10n_ve_global_discount_tax_ids = fields.Many2many(
        comodel_name="account.tax",
        relation="account_move_line_l10n_ve_global_discount_tax_rel",
        column1="line_id",
        column2="tax_id",
        string="Global discount tax group",
        readonly=True,
        copy=False,
    )
    l10n_ve_global_discount_allocation_key = fields.Binary(
        compute="_compute_l10n_ve_global_discount_allocation_key",
        exportable=False,
    )
    l10n_ve_line_discount_allocation_key = fields.Binary(
        compute="_compute_l10n_ve_line_discount_allocation_key",
        exportable=False,
    )
    l10n_ve_price_subtotal_wo_discount = fields.Monetary(
        string="Subtotal sin descuento",
        compute="_compute_l10n_ve_price_subtotal_wo_discount",
        currency_field="currency_id",
    )
    l10n_ve_price_subtotal_wo_discount_currency = fields.Monetary(
        string="Subtotal sin descuento (compañía)",
        compute="_compute_l10n_ve_price_subtotal_wo_discount",
        currency_field="company_currency_id",
    )
    l10n_ve_price_discount = fields.Monetary(
        string="Descuento",
        compute="_compute_l10n_ve_price_subtotal_wo_discount",
        currency_field="currency_id",
    )
    l10n_ve_price_discount_currency = fields.Monetary(
        string="Descuento (compañía)",
        compute="_compute_l10n_ve_price_subtotal_wo_discount",
        currency_field="company_currency_id",
    )

    @api.depends(
        "quantity",
        "price_unit",
        "discount",
        "price_subtotal",
        "currency_id",
        "company_currency_id",
        "subtotal_company_currency",
        "currency_rate",
    )
    def _compute_l10n_ve_price_subtotal_wo_discount(self):
        for line in self:
            qty = line.quantity or 0.0
            price_unit = line.price_unit or 0.0
            amount = qty * price_unit
            if line.currency_id:
                amount = line.currency_id.round(amount)
            line.l10n_ve_price_subtotal_wo_discount = amount
            discount_doc = amount - (line.price_subtotal or 0.0)
            if line.currency_id:
                discount_doc = line.currency_id.round(discount_doc)
            line.l10n_ve_price_discount = discount_doc

            discount_factor = 1.0 - ((line.discount or 0.0) / 100.0)
            company_subtotal = line.subtotal_company_currency or 0.0
            if discount_factor:
                amount_company = company_subtotal / discount_factor
            else:
                rate = line.currency_rate or 1.0
                amount_company = amount * rate if rate else amount
            if line.company_currency_id:
                amount_company = line.company_currency_id.round(amount_company)
            line.l10n_ve_price_subtotal_wo_discount_currency = amount_company
            discount_company = amount_company - company_subtotal
            if line.company_currency_id:
                discount_company = line.company_currency_id.round(discount_company)
            line.l10n_ve_price_discount_currency = discount_company

    @api.depends(
        "l10n_ve_global_discount_line",
        "l10n_ve_global_discount_tax_ids",
        "account_id",
        "move_id",
        "currency_rate",
        "display_type",
    )
    def _compute_l10n_ve_global_discount_allocation_key(self):
        for line in self:
            if (
                line.l10n_ve_global_discount_line
                and line.display_type == "global_discount"
                and line.move_id
            ):
                line.l10n_ve_global_discount_allocation_key = frozendict(
                    {
                        "move_id": line.move_id.id,
                        "account_id": line.account_id.id,
                        "currency_rate": line.currency_rate,
                        "tax_ids": tuple(
                            sorted(line.l10n_ve_global_discount_tax_ids.ids)
                        ),
                    }
                )
            else:
                line.l10n_ve_global_discount_allocation_key = False

    @api.depends(
        "l10n_ve_line_discount_line",
        "l10n_ve_global_discount_tax_ids",
        "account_id",
        "move_id",
        "currency_rate",
        "display_type",
    )
    def _compute_l10n_ve_line_discount_allocation_key(self):
        for line in self:
            if (
                line.l10n_ve_line_discount_line
                and line.display_type == "discount"
                and line.move_id
            ):
                line.l10n_ve_line_discount_allocation_key = frozendict(
                    {
                        "move_id": line.move_id.id,
                        "account_id": line.account_id.id,
                        "currency_rate": line.currency_rate,
                        "tax_ids": tuple(
                            sorted(line.l10n_ve_global_discount_tax_ids.ids)
                        ),
                    }
                )
            else:
                line.l10n_ve_line_discount_allocation_key = False

    @api.depends("account_id", "company_id")
    def _compute_discount_allocation_key(self):
        res = super()._compute_discount_allocation_key()
        for line in self.filtered(
            lambda aml: aml.l10n_ve_global_discount_line
            or aml.l10n_ve_line_discount_line
        ):
            line.discount_allocation_key = False
        return res

    @api.depends(
        "account_id",
        "company_id",
        "discount",
        "price_unit",
        "quantity",
        "currency_rate",
        "analytic_distribution",
    )
    def _compute_discount_allocation_needed(self):
        ve_journal_lines = self.filtered(
            lambda line: line.move_id._l10n_ve_uses_global_discount_journal_lines()
        )
        res = super(
            AccountMoveLine, self - ve_journal_lines
        )._compute_discount_allocation_needed()
        for line in ve_journal_lines:
            line.discount_allocation_needed = False
            line.discount_allocation_dirty = True
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        res._l10n_ve_refresh_move_global_discounts()
        return res

    def write(self, vals):
        res = super().write(vals)
        if set(vals) & {
            "price_unit",
            "quantity",
            "discount",
            "tax_ids",
            "product_id",
            "display_type",
        }:
            self._l10n_ve_refresh_move_global_discounts()
        return res

    def unlink(self):
        moves = self.move_id
        res = super().unlink()
        if self.env.context.get("dynamic_unlink") or self.env.context.get(
            "l10n_ve_skip_discount_refresh"
        ):
            return res
        moves._l10n_ve_refresh_global_discounts_from_lines()
        return res

    def _l10n_ve_refresh_move_global_discounts(self):
        if self.env.context.get("l10n_ve_skip_discount_refresh"):
            return
        product_lines = self.filtered(
            lambda line: line.display_type not in ("line_section", "line_note")
            and not line.tax_line_id
        )
        if product_lines:
            product_lines.move_id._l10n_ve_refresh_global_discounts_from_lines()

    @api.constrains("discount", "move_id")
    def _l10n_ve_check_line_discount(self):
        prec = self.env["decimal.precision"].precision_get("Discount")
        for line in self:
            if line.display_type != "product":
                continue
            if line.move_id.move_type == "entry":
                continue
            if line.move_id.country_code != "VE":
                continue
            disc = line.discount or 0.0
            if float_compare(disc, 100.0, precision_digits=prec) >= 0:
                raise ValidationError(
                    _(
                        "No se permite un descuento del 100%% en la línea de factura. "
                        'La línea "%(line)s" tiene %(discount)s%%.'
                    )
                    % {
                        "line": line.name or _("Sin nombre"),
                        "discount": disc,
                    }
                )
