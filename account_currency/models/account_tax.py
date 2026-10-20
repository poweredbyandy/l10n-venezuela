# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_base_line_grouping_key(self, base_line):
        res = super()._prepare_base_line_grouping_key(base_line)
        res["price_subtotal_currency"] = base_line["price_subtotal_currency"]
        return res

    @api.model
    def _prepare_base_line_for_taxes_computation(self, record, **kwargs):
        res = super()._prepare_base_line_for_taxes_computation(record, **kwargs)
        res["price_subtotal_currency"] = self._get_base_line_field_value_from_record(
            record, "price_subtotal_currency", kwargs, 0.0
        )
        return res

    @api.model
    def _add_tax_details_in_base_line(self, base_line, company, rounding_method=None):
        """Convert the company line base from the rounded foreign subtotal.

        Standard Odoo converts ``price_unit * qty`` (unrounded foreign) with the
        rate, so company-currency line balances can disagree with
        ``round(foreign_subtotal) / rate``. Only the excluded base is aligned.
        Tax amounts stay as Odoo computed them.
        """
        super()._add_tax_details_in_base_line(
            base_line, company, rounding_method=rounding_method
        )
        self._l10n_ve_align_company_amounts_from_rounded_foreign(base_line, company)

    @api.model
    def _l10n_ve_align_company_amounts_from_rounded_foreign(self, base_line, company):
        currency = base_line.get("currency_id")
        company_currency = company.currency_id
        rate = base_line.get("rate") or 0.0
        tax_details = base_line.get("tax_details")
        if (
            not tax_details
            or not currency
            or not company_currency
            or not rate
            or currency == company_currency
        ):
            return

        def to_company(amount_currency):
            return company_currency.round(currency.round(amount_currency) / rate)

        tax_details["raw_total_excluded"] = to_company(
            tax_details["raw_total_excluded_currency"]
        )
        for tax_data in tax_details.get("taxes_data") or []:
            tax_data["raw_base_amount"] = to_company(
                tax_data["raw_base_amount_currency"]
            )
        tax_details["raw_total_included"] = company_currency.round(
            tax_details["raw_total_excluded"]
            + sum(
                tax_data["raw_tax_amount"]
                for tax_data in tax_details.get("taxes_data") or []
            )
        )
