# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.tools import float_is_zero


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _add_tax_details_in_base_line(self, base_line, company, rounding_method=None):
        super()._add_tax_details_in_base_line(
            base_line, company, rounding_method=rounding_method
        )
        company_pu = base_line.get("l10n_ve_company_price_unit")
        forced_excluded = base_line.get("l10n_ve_company_total_excluded")
        if company_pu is None and forced_excluded is None:
            return
        rounding_method = rounding_method or company.tax_calculation_rounding_method
        if forced_excluded is not None:
            price_unit_after_discount = forced_excluded
            quantity_for_tax = 1.0
        else:
            price_unit_after_discount = company_pu * (
                1 - ((base_line.get("discount") or 0.0) / 100.0)
            )
            quantity_for_tax = base_line["quantity"]
        taxes_computation = base_line["tax_ids"]._get_tax_details(
            price_unit=price_unit_after_discount,
            quantity=quantity_for_tax,
            precision_rounding=company.currency_id.rounding,
            rounding_method=rounding_method,
            product=base_line["product_id"],
            product_uom=base_line["product_uom_id"],
            special_mode=base_line["special_mode"],
            manual_tax_amounts=base_line["manual_tax_amounts"],
            filter_tax_function=base_line["filter_tax_function"],
        )
        if forced_excluded is not None:
            # Keep the forced company base; only tax amounts come from computation.
            taxes_computation = dict(taxes_computation)
            tax_total = sum(
                tax_data["tax_amount"] for tax_data in taxes_computation["taxes_data"]
            )
            taxes_computation["total_excluded"] = forced_excluded
            taxes_computation["total_included"] = company.currency_id.round(
                forced_excluded + tax_total
            )
            for tax_data in taxes_computation["taxes_data"]:
                tax_data["base_amount"] = forced_excluded
        tax_details = base_line["tax_details"]
        tax_details["raw_total_excluded"] = taxes_computation["total_excluded"]
        tax_details["raw_total_included"] = taxes_computation["total_included"]
        if rounding_method == "round_per_line":
            tax_details["raw_total_excluded"] = company.currency_id.round(
                tax_details["raw_total_excluded"]
            )
            tax_details["raw_total_included"] = company.currency_id.round(
                tax_details["raw_total_included"]
            )
        for tax_data_company, tax_data in zip(
            taxes_computation["taxes_data"],
            tax_details["taxes_data"],
            strict=False,
        ):
            tax_amount = tax_data_company["tax_amount"]
            base_amount = tax_data_company["base_amount"]
            if rounding_method == "round_per_line":
                tax_amount = company.currency_id.round(tax_amount)
                base_amount = company.currency_id.round(base_amount)
            tax_data["raw_tax_amount"] = tax_amount
            tax_data["raw_base_amount"] = base_amount

    @api.model
    def _account_currency_document_rate(self, document):
        if document._name == "account.move":
            return document.invoice_currency_rate or 0.0
        return getattr(document, "currency_rate", None) or 0.0

    @api.model
    def _account_currency_order_lines(self, document):
        if document._name in ("sale.order", "purchase.order"):
            return document.order_line.filtered(lambda line: not line.display_type)
        return []

    @api.model
    def _account_currency_line_taxes(self, line):
        if "tax_id" in line._fields:
            return line.tax_id
        if "taxes_id" in line._fields:
            return line.taxes_id
        return self.env["account.tax"]

    @api.model
    def _account_currency_line_company_subtotal(self, document, line):
        """Same company subtotal rule as invoice ``price_subtotal_currency``."""
        company_currency = document.company_id.currency_id
        currency = document.currency_id
        foreign_subtotal = currency.round(line.price_subtotal or 0.0)
        if currency == company_currency:
            return company_currency.round(foreign_subtotal)
        rate = self._account_currency_document_rate(document)
        if not rate:
            return 0.0
        return company_currency.round(foreign_subtotal / rate)

    @api.model
    def _account_currency_order_company_base_by_tax_group(self, document):
        """Map tax.group id → company base from per-line rounded conversion."""
        company_currency = document.company_id.currency_id
        base_by_group = {}
        total_base = 0.0
        for line in self._account_currency_order_lines(document):
            company_subtotal = self._account_currency_line_company_subtotal(
                document, line
            )
            total_base = company_currency.round(total_base + company_subtotal)
            taxes = self._account_currency_line_taxes(line)
            for group in taxes.tax_group_id:
                base_by_group[group.id] = company_currency.round(
                    base_by_group.get(group.id, 0.0) + company_subtotal
                )
        return base_by_group, total_base

    @api.model
    def _account_currency_align_order_tax_totals(self, document, totals):
        """Force order TaxTotals company amounts to invoice-like per-line rounding.

        Sale/purchase tax engine convert then aggregate; invoices round each line
        to company currency then book. Match that so the order footer preview
        equals the invoice that will be created with the same rate.
        """
        if document._name not in ("sale.order", "purchase.order") or not totals:
            return totals
        company_currency = document.company_id.currency_id
        if not document.currency_id or document.currency_id == company_currency:
            return totals

        base_by_group, total_base = (
            self._account_currency_order_company_base_by_tax_group(document)
        )
        totals = dict(totals)
        subtotals = []
        tax_amount = 0.0
        base_amount = 0.0
        for subtotal in totals.get("subtotals") or []:
            subtotal = dict(subtotal)
            tax_groups = []
            subtotal_tax = 0.0
            subtotal_base = 0.0
            for group in subtotal.get("tax_groups") or []:
                group = dict(group)
                group_id = group.get("id")
                group_new_base = base_by_group.get(group_id)
                if group_new_base is None:
                    tax_groups.append(group)
                    subtotal_tax = company_currency.round(
                        subtotal_tax + (group.get("tax_amount") or 0.0)
                    )
                    subtotal_base = company_currency.round(
                        subtotal_base + (group.get("base_amount") or 0.0)
                    )
                    continue
                group_base_currency = group.get("base_amount_currency") or 0.0
                group_tax_currency = group.get("tax_amount_currency") or 0.0
                tax_ids = group.get("involved_tax_ids") or []
                percent = 0.0
                if tax_ids:
                    taxes = self.browse(tax_ids).flatten_taxes_hierarchy()
                    percent = (
                        sum(tax.amount for tax in taxes if tax.amount_type == "percent")
                        / 100.0
                    )
                if not percent and group_base_currency:
                    percent = group_tax_currency / group_base_currency
                elif not percent and group.get("base_amount"):
                    percent = (group.get("tax_amount") or 0.0) / group["base_amount"]
                group_tax = company_currency.round(group_new_base * percent)
                group["base_amount"] = group_new_base
                group["tax_amount"] = group_tax
                if group.get("display_base_amount") not in (None, False):
                    group["display_base_amount"] = group_new_base
                tax_groups.append(group)
                subtotal_tax = company_currency.round(subtotal_tax + group_tax)
                subtotal_base = company_currency.round(subtotal_base + group_new_base)
            subtotal["tax_groups"] = tax_groups
            subtotal["base_amount"] = subtotal_base or total_base
            subtotal["tax_amount"] = subtotal_tax
            subtotals.append(subtotal)
            tax_amount = company_currency.round(tax_amount + subtotal_tax)
            base_amount = company_currency.round(base_amount + subtotal_base)

        if float_is_zero(base_amount, precision_rounding=company_currency.rounding):
            base_amount = total_base
        else:
            # Keep untaxed lines in the company base (tax groups omit them).
            base_amount = total_base

        totals["subtotals"] = subtotals
        totals["base_amount"] = base_amount
        totals["tax_amount"] = tax_amount
        totals["total_amount"] = company_currency.round(base_amount + tax_amount)
        totals["display_in_company_currency"] = True
        if not totals.get("company_currency_id"):
            totals["company_currency_id"] = company_currency.id
        return totals
