# Part of Odoo. See LICENSE file for full copyright and licensing details.

from contextlib import contextmanager

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    l10n_ve_manual_untaxed_currency = fields.Monetary(
        string="Manual untaxed amount",
        currency_field="currency_id",
        copy=False,
    )
    l10n_ve_manual_untaxed_currency_active = fields.Boolean(
        string="Manual untaxed amount in document currency",
        copy=False,
    )
    l10n_ve_manual_untaxed_company = fields.Monetary(
        string="Manual untaxed amount in company currency",
        currency_field="company_currency_id",
        copy=False,
    )
    l10n_ve_manual_untaxed_company_active = fields.Boolean(
        string="Manual untaxed amount in company currency active",
        copy=False,
    )
    l10n_ve_manual_balance_active = fields.Boolean(
        string="Manual company balance",
        copy=False,
    )

    @api.depends(
        "l10n_ve_manual_untaxed_company",
        "l10n_ve_manual_untaxed_company_active",
    )
    def _compute_price_subtotal_currency(self):
        manual_lines = self.filtered("l10n_ve_manual_untaxed_company_active")
        for line in manual_lines:
            line.price_subtotal_currency = line.l10n_ve_manual_untaxed_company
        super(
            AccountMoveLine, self - manual_lines
        )._compute_price_subtotal_currency()

    @contextmanager
    def _sync_invoice(self, container):
        forced = container["records"].filtered("l10n_ve_manual_balance_active")
        with self.env.protecting([self._fields["balance"]], forced):
            with super()._sync_invoice(container):
                yield

    def write(self, vals):
        if (
            {"price_unit", "quantity", "discount"} & set(vals)
            and not self.env.context.get("l10n_ve_keep_manual_tax_totals")
        ):
            vals = dict(vals)
            vals.setdefault("l10n_ve_manual_untaxed_currency_active", False)
            vals.setdefault("l10n_ve_manual_untaxed_company_active", False)
            vals.setdefault("l10n_ve_manual_balance_active", False)
        return super().write(vals)
