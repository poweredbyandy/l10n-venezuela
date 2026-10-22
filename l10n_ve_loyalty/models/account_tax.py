# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.tools import float_is_zero


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _l10n_ve_get_document_currency_rate(self, document):
        if document._name == "account.move":
            return document.invoice_currency_rate or 1.0
        if document._name == "sale.order":
            return document.currency_rate or 1.0
        return 1.0

    @api.model
    def _l10n_ve_get_document_conversion_date(self, document):
        if document._name == "account.move":
            return document.invoice_date or document.date
        if document._name == "sale.order":
            return (document.date_order or fields.Datetime.now()).date()
        return fields.Date.context_today(self.env)

    @api.model
    def _l10n_ve_amount_currency_to_company(self, document, amount_currency):
        """Convert an amount in document currency to company currency."""
        currency = document.currency_id
        company = document.company_id
        if not currency or currency == company.currency_id:
            return amount_currency
        inverse_rate = getattr(document, "l10n_ve_inverse_rate", None) or 0.0
        if inverse_rate:
            return company.currency_id.round(amount_currency * inverse_rate)
        rate = self._l10n_ve_get_document_currency_rate(document) or 0.0
        if rate:
            return company.currency_id.round(amount_currency / rate)
        conversion_date = self._l10n_ve_get_document_conversion_date(document)
        return currency._convert(
            amount_currency,
            company.currency_id,
            company,
            conversion_date,
        )

    @api.model
    def _l10n_ve_document_product_subtotal_company(self, document):
        """Sum product-line company subtotals shown before global discount.

        Keeps the tax-totals "Subtotal" in company currency equal to the sum of
        invoice/order line company amounts the user sees above the footer.
        Excludes discount-product lines so the gross is pre-discount.
        """
        company_currency = document.company_id.currency_id
        if document._name == "account.move":
            lines = document.invoice_line_ids.filtered(
                lambda line: line.display_type == "product"
            )
            if hasattr(document, "_l10n_ve_get_product_discount_lines"):
                lines -= document._l10n_ve_get_product_discount_lines()
            if not lines or "price_subtotal_currency" not in lines._fields:
                return None
            return company_currency.round(sum(lines.mapped("price_subtotal_currency")))
        if document._name == "sale.order":
            lines = document.order_line.filtered(lambda line: not line.display_type)
            if not lines or "price_subtotal_currency" not in lines._fields:
                return None
            return company_currency.round(sum(lines.mapped("price_subtotal_currency")))
        return None

    @api.model
    def _l10n_ve_company_global_discount_amount(
        self, document, subtotal_gross, global_discount_lines
    ):
        """Apply global discounts on the company-currency gross (Bs).

        Percentage discounts use the company gross so ``gross - discount`` and
        ``gross * %`` stay consistent in Bs. Fixed amounts are converted from
        document currency with the document rate.
        """
        company_currency = document.company_id.currency_id
        running = subtotal_gross
        total = 0.0
        for line in global_discount_lines:
            if float_is_zero(running, precision_rounding=company_currency.rounding):
                break
            if line.get("discount_type") == "percentage" and line.get(
                "discount_percentage"
            ):
                amount = company_currency.round(
                    running * line["discount_percentage"]
                )
            else:
                amount = self._l10n_ve_amount_currency_to_company(
                    document, line.get("amount") or 0.0
                )
                amount = min(amount, running)
            if float_is_zero(amount, precision_rounding=company_currency.rounding):
                continue
            total = company_currency.round(total + amount)
            running = company_currency.round(running - amount)
        return total

    @api.model
    def _l10n_ve_realign_company_tax_totals_after_discount(
        self, document, totals, subtotal_gross, global_discount_amount
    ):
        """Force company base/tax/total to follow gross - discount in Bs."""
        company_currency = document.company_id.currency_id
        new_base = company_currency.round(subtotal_gross - global_discount_amount)
        old_base = totals.get("base_amount") or 0.0
        if float_is_zero(old_base, precision_rounding=company_currency.rounding):
            return totals

        subtotals = []
        tax_amount = 0.0
        for subtotal in totals.get("subtotals") or []:
            subtotal = dict(subtotal)
            tax_groups = []
            subtotal_tax = 0.0
            subtotal_base = 0.0
            for group in subtotal.get("tax_groups") or []:
                group = dict(group)
                group_old_base = group.get("base_amount") or 0.0
                if float_is_zero(
                    old_base, precision_rounding=company_currency.rounding
                ):
                    group_new_base = new_base
                else:
                    group_new_base = company_currency.round(
                        new_base * group_old_base / old_base
                    )
                group_base_currency = group.get("base_amount_currency") or 0.0
                group_tax_currency = group.get("tax_amount_currency") or 0.0
                tax_ids = group.get("involved_tax_ids") or []
                percent = 0.0
                if tax_ids:
                    taxes = self.browse(tax_ids).flatten_taxes_hierarchy()
                    percent = sum(
                        tax.amount
                        for tax in taxes
                        if tax.amount_type == "percent"
                    ) / 100.0
                if not percent and group_base_currency:
                    percent = group_tax_currency / group_base_currency
                elif not percent and group_old_base:
                    percent = (group.get("tax_amount") or 0.0) / group_old_base
                group_tax = company_currency.round(group_new_base * percent)
                group["base_amount"] = group_new_base
                group["tax_amount"] = group_tax
                if group.get("display_base_amount") not in (None, False):
                    group["display_base_amount"] = group_new_base
                tax_groups.append(group)
                subtotal_tax = company_currency.round(subtotal_tax + group_tax)
                subtotal_base = company_currency.round(
                    subtotal_base + group_new_base
                )
            subtotal["tax_groups"] = tax_groups
            subtotal["base_amount"] = subtotal_base or new_base
            subtotal["tax_amount"] = subtotal_tax
            subtotals.append(subtotal)
            tax_amount = company_currency.round(tax_amount + subtotal_tax)

        totals["subtotals"] = subtotals
        totals["base_amount"] = new_base
        totals["tax_amount"] = tax_amount
        totals["total_amount"] = company_currency.round(new_base + tax_amount)
        return totals

    @api.model
    def _l10n_ve_uses_legacy_company_discount_totals(self, document):
        return (
            document._name == "account.move"
            and document.l10n_ve_legacy_company_discount_totals
            and document.currency_id != document.company_id.currency_id
        )

    @api.model
    def _l10n_ve_uses_accounting_company_totals(self, document):
        return (
            document._name == "account.move"
            and document.currency_id != document.company_id.currency_id
        )

    @api.model
    def _l10n_ve_accounting_amounts_for_tax_group(self, move, tax_group_id):
        if not move or not tax_group_id or tax_group_id == -1:
            return None
        company_currency = move.company_id.currency_id
        tax_lines = move.line_ids.filtered(
            lambda line: line.tax_line_id
            and line.tax_line_id.tax_group_id.id == tax_group_id
        )
        if tax_lines:
            return {
                "base_amount": company_currency.round(
                    abs(sum(tax_lines.mapped("tax_base_amount")))
                ),
                "tax_amount": company_currency.round(
                    abs(sum(tax_lines.mapped("balance")))
                ),
            }
        base_lines = move.line_ids.filtered(
            lambda line: line.display_type in ("product", "global_discount")
            and tax_group_id in line.tax_ids.tax_group_id.ids
        )
        if not base_lines:
            return None
        return {
            "base_amount": company_currency.round(
                abs(sum(base_lines.mapped("balance")))
            ),
            "tax_amount": 0.0,
        }

    @api.model
    def _l10n_ve_align_tax_totals_groups_to_accounting(self, document, totals):
        if not self._l10n_ve_uses_accounting_company_totals(document):
            return totals
        if not document.line_ids:
            return totals
        company_currency = document.company_id.currency_id
        old_base = totals.get("base_amount") or 0.0
        old_tax = totals.get("tax_amount") or 0.0
        subtotals = []
        tax_amount = 0.0
        base_amount = 0.0
        aligned = False
        for subtotal in totals.get("subtotals") or []:
            subtotal = dict(subtotal)
            tax_groups = []
            subtotal_tax = 0.0
            subtotal_base = 0.0
            for group in subtotal.get("tax_groups") or []:
                group = dict(group)
                amounts = self._l10n_ve_accounting_amounts_for_tax_group(
                    document, group.get("id")
                )
                if amounts:
                    group["base_amount"] = amounts["base_amount"]
                    group["tax_amount"] = amounts["tax_amount"]
                    if group.get("display_base_amount") not in (None, False):
                        group["display_base_amount"] = amounts["base_amount"]
                    aligned = True
                tax_groups.append(group)
                subtotal_tax = company_currency.round(
                    subtotal_tax + (group.get("tax_amount") or 0.0)
                )
                subtotal_base = company_currency.round(
                    subtotal_base + (group.get("base_amount") or 0.0)
                )
            subtotal["tax_groups"] = tax_groups
            subtotal["base_amount"] = subtotal_base
            subtotal["tax_amount"] = subtotal_tax
            subtotals.append(subtotal)
            tax_amount = company_currency.round(tax_amount + subtotal_tax)
            base_amount = company_currency.round(base_amount + subtotal_base)
        if not aligned:
            return totals
        totals["subtotals"] = subtotals
        totals["base_amount"] = base_amount
        totals["tax_amount"] = tax_amount
        totals["total_amount"] = company_currency.round(
            (totals.get("total_amount") or 0.0)
            + (base_amount - old_base)
            + (tax_amount - old_tax)
        )
        return totals

    @api.model
    def _l10n_ve_align_company_base_to_accounting(self, document, totals, new_base):
        company_currency = document.company_id.currency_id
        delta = company_currency.round(new_base - (totals.get("base_amount") or 0.0))
        if float_is_zero(delta, precision_rounding=company_currency.rounding):
            return totals

        subtotals = []
        for subtotal in totals.get("subtotals") or []:
            subtotal = dict(subtotal)
            tax_groups = [dict(group) for group in subtotal.get("tax_groups") or []]
            weights = [group.get("base_amount") or 0.0 for group in tax_groups]
            parts = document._l10n_ve_split_amount_by_weights(
                delta, weights, currency=company_currency
            )
            for group, part in zip(tax_groups, parts, strict=False):
                group["base_amount"] = company_currency.round(
                    (group.get("base_amount") or 0.0) + part
                )
                if group.get("display_base_amount") not in (None, False):
                    group["display_base_amount"] = company_currency.round(
                        group["display_base_amount"] + part
                    )
            subtotal["tax_groups"] = tax_groups
            subtotal["base_amount"] = company_currency.round(
                (subtotal.get("base_amount") or 0.0) + delta
            )
            subtotals.append(subtotal)

        totals["subtotals"] = subtotals
        totals["base_amount"] = new_base
        totals["total_amount"] = company_currency.round(
            (totals.get("total_amount") or 0.0) + delta
        )
        return totals

    @api.model
    def _l10n_ve_build_discount_totals_result(
        self,
        document,
        tax_totals,
        global_discount_amount_currency,
        global_discount_lines,
    ):
        base_amount_currency = tax_totals.get("base_amount_currency", 0.0)
        base_amount = tax_totals.get("base_amount", 0.0)
        base_amount_foreign = tax_totals.get("base_amount_foreign_currency")
        currency = document.currency_id
        if float_is_zero(
            global_discount_amount_currency,
            precision_rounding=currency.rounding,
        ):
            return {
                "show_global_discount": False,
                "global_discount_amount_currency": 0.0,
                "global_discount_amount": 0.0,
                "global_discount_amount_foreign": 0.0,
                "global_discount_percentage": False,
                "subtotal_gross_currency": base_amount_currency,
                "subtotal_gross": base_amount,
                "subtotal_gross_foreign": base_amount_foreign or 0.0,
                "global_discount_lines": [],
                "realign_company_tax_totals": False,
            }

        company = document.company_id
        company_currency = company.currency_id
        product_subtotal_company = self._l10n_ve_document_product_subtotal_company(
            document
        )
        realign_company_tax_totals = False
        accounting_company_base = None
        if product_subtotal_company is not None and document._name == "account.move":
            subtotal_gross = product_subtotal_company
            accounting_company_base = company_currency.round(
                abs(document.amount_untaxed_signed)
            )
            global_discount_amount = company_currency.round(
                subtotal_gross - accounting_company_base
            )
        elif product_subtotal_company is not None:
            subtotal_gross = product_subtotal_company
            global_discount_amount = self._l10n_ve_company_global_discount_amount(
                document, subtotal_gross, global_discount_lines
            )
            realign_company_tax_totals = document.currency_id != company_currency
        else:
            global_discount_amount = self._l10n_ve_amount_currency_to_company(
                document, global_discount_amount_currency
            )
            subtotal_gross = company_currency.round(
                base_amount + global_discount_amount
            )

        global_discount_amount_foreign = 0.0
        if document._name == "account.move":
            foreign_currency = getattr(
                document, "foreign_currency_id", False
            ) or getattr(company, "foreign_currency_id", False)
        else:
            foreign_currency = getattr(company, "foreign_currency_id", False)
        conversion_date = self._l10n_ve_get_document_conversion_date(document)
        if foreign_currency and base_amount_foreign is not None:
            global_discount_amount_foreign = currency._convert(
                global_discount_amount_currency,
                foreign_currency,
                company,
                conversion_date,
            )

        subtotal_gross_currency = base_amount_currency + global_discount_amount_currency
        overall_percentage = False
        percentage_lines = [
            line
            for line in global_discount_lines
            if line.get("discount_type") == "percentage"
            and line.get("discount_percentage")
        ]
        if (
            percentage_lines
            and len(percentage_lines) == len(global_discount_lines)
            and not float_is_zero(
                subtotal_gross_currency, precision_rounding=currency.rounding
            )
        ):
            if len(percentage_lines) == 1:
                overall_percentage = percentage_lines[0]["discount_percentage"]
            else:
                overall_percentage = (
                    global_discount_amount_currency / subtotal_gross_currency
                )
        return {
            "show_global_discount": True,
            "global_discount_amount_currency": global_discount_amount_currency,
            "global_discount_amount": global_discount_amount,
            "global_discount_amount_foreign": global_discount_amount_foreign,
            "global_discount_percentage": overall_percentage,
            "subtotal_gross_currency": subtotal_gross_currency,
            "subtotal_gross": subtotal_gross,
            "subtotal_gross_foreign": (base_amount_foreign or 0.0)
            + global_discount_amount_foreign,
            "global_discount_lines": global_discount_lines,
            "realign_company_tax_totals": realign_company_tax_totals,
            "accounting_company_base": accounting_company_base,
        }

    @api.model
    def _l10n_ve_apply_global_discount_to_tax_totals(self, document, tax_totals):
        """Return a new tax_totals dict with VE global discount display fields."""
        if not tax_totals:
            return tax_totals
        totals = dict(tax_totals)
        discount_totals = self._l10n_ve_get_global_discount_totals(document, totals)
        totals["l10n_ve_show_global_discount"] = discount_totals["show_global_discount"]
        totals["l10n_ve_subtotal_gross_currency"] = discount_totals[
            "subtotal_gross_currency"
        ]
        totals["l10n_ve_subtotal_gross"] = discount_totals["subtotal_gross"]
        totals["l10n_ve_global_discount_amount_currency"] = discount_totals[
            "global_discount_amount_currency"
        ]
        totals["l10n_ve_global_discount_amount"] = discount_totals[
            "global_discount_amount"
        ]
        totals["l10n_ve_global_discount_amount_foreign"] = discount_totals[
            "global_discount_amount_foreign"
        ]
        totals["l10n_ve_subtotal_gross_foreign"] = discount_totals[
            "subtotal_gross_foreign"
        ]
        totals["l10n_ve_global_discount_lines"] = discount_totals[
            "global_discount_lines"
        ]
        totals["l10n_ve_global_discount_percentage"] = discount_totals[
            "global_discount_percentage"
        ]
        if (
            discount_totals.get("realign_company_tax_totals")
            and document._name != "account.move"
        ):
            totals = self._l10n_ve_realign_company_tax_totals_after_discount(
                document,
                totals,
                discount_totals["subtotal_gross"],
                discount_totals["global_discount_amount"],
            )
        elif discount_totals.get("accounting_company_base") is not None:
            totals = self._l10n_ve_align_company_base_to_accounting(
                document,
                totals,
                discount_totals["accounting_company_base"],
            )
        totals = self._l10n_ve_align_tax_totals_groups_to_accounting(document, totals)
        can_manage = self.env.user.has_group(
            "l10n_ve_loyalty.group_l10n_ve_global_discount"
        )
        if document._name == "sale.order" and self.env.user.has_group(
            "sale.group_discount_per_so_line"
        ):
            can_manage = True
        totals["l10n_ve_can_manage_global_discount"] = can_manage
        company_currency = document.company_id.currency_id
        totals["display_in_company_currency"] = bool(
            document.currency_id and document.currency_id != company_currency
        )
        if not totals.get("company_currency_id") and company_currency:
            totals["company_currency_id"] = company_currency.id
        return totals

    @api.model
    def _l10n_ve_get_product_line_discount_totals(self, document, tax_totals):
        """Build tax-totals discount data from sale_discount_product lines."""
        if not hasattr(document, "_l10n_ve_get_product_discount_lines"):
            return None
        lines = document._l10n_ve_get_product_discount_lines()
        if not lines:
            return None
        currency = document.currency_id
        global_discount_lines = []
        total_amount = 0.0
        line_amounts = []
        for line in lines:
            line_amount = abs(line.price_subtotal or 0.0)
            if float_is_zero(line_amount, precision_rounding=currency.rounding):
                continue
            total_amount += line_amount
            line_amounts.append((line, currency.round(line_amount)))
        if not line_amounts:
            return None
        base_amount_currency = tax_totals.get("base_amount_currency", 0.0) or 0.0
        gross = base_amount_currency + total_amount
        for line, line_amount in line_amounts:
            discount_percentage = False
            discount_type = "fixed"
            if not float_is_zero(gross, precision_rounding=currency.rounding):
                discount_percentage = line_amount / gross
                discount_type = "percentage"
            global_discount_lines.append(
                {
                    "id": line.id,
                    "name": _("Descuento"),
                    "amount": line_amount,
                    "discount_type": discount_type,
                    "discount_percentage": discount_percentage,
                    "source": "product_line",
                }
            )
        return self._l10n_ve_build_discount_totals_result(
            document,
            tax_totals,
            currency.round(total_amount),
            global_discount_lines,
        )

    @api.model
    def _l10n_ve_get_global_discount_totals(self, document, tax_totals):
        """Compute grouped global discount amounts for VE tax totals display.

        Prefers SENIAT global discount records; if none, falls back to product
        discount lines (sale_discount_product_id) so both modes share tax totals UI.
        """
        base_amount_currency = tax_totals.get("base_amount_currency", 0.0)
        base_amount = tax_totals.get("base_amount", 0.0)
        base_amount_foreign = tax_totals.get("base_amount_foreign_currency")
        empty_result = {
            "show_global_discount": False,
            "global_discount_amount_currency": 0.0,
            "global_discount_amount": 0.0,
            "global_discount_amount_foreign": 0.0,
            "global_discount_percentage": False,
            "subtotal_gross_currency": base_amount_currency,
            "subtotal_gross": base_amount,
            "subtotal_gross_foreign": base_amount_foreign or 0.0,
            "global_discount_lines": [],
        }
        discounts = document.l10n_ve_global_discount_ids
        if discounts:
            subtotal_by_taxes = document._l10n_ve_global_discount_subtotal_by_taxes()
            global_discount_lines = document._l10n_ve_get_global_discount_lines_data(
                subtotal_by_taxes
            )
            global_discount_amount_currency = sum(
                line["amount"] for line in global_discount_lines
            )
            return self._l10n_ve_build_discount_totals_result(
                document,
                tax_totals,
                global_discount_amount_currency,
                global_discount_lines,
            )

        product_line_totals = self._l10n_ve_get_product_line_discount_totals(
            document, tax_totals
        )
        if product_line_totals:
            return product_line_totals
        return empty_result

    @api.model
    def _l10n_ve_get_line_discount_amounts(self, base_lines, company):
        """Return untaxed line discount amounts in company currency by move line id."""
        if not base_lines:
            return {}

        discounted_lines = [
            base_line
            for base_line in base_lines
            if (base_line.get("discount") or 0.0) > 0.0
            and base_line.get("special_type") != "global_discount"
        ]
        if not discounted_lines:
            return {}

        for in_foreign_currency in (True, False):
            self._add_and_round_raw_gross_total_excluded_and_discount(
                base_lines,
                company,
                in_foreign_currency=in_foreign_currency,
            )

        amounts = {}
        for base_line in discounted_lines:
            record = base_line.get("record")
            line_id = record.id if getattr(record, "id", False) else base_line.get("id")
            if not line_id:
                continue
            amount = base_line["tax_details"].get("raw_discount_amount", 0.0)
            if amount:
                amounts[line_id] = amount
        return amounts
