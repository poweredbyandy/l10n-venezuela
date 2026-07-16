# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
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
    def _l10n_ve_get_global_discount_totals(self, document, tax_totals):
        """Compute grouped global discount amounts for VE tax totals display."""
        base_amount_currency = tax_totals.get("base_amount_currency", 0.0)
        base_amount = tax_totals.get("base_amount", 0.0)
        base_amount_foreign = tax_totals.get("base_amount_foreign_currency")
        discounts = document.l10n_ve_global_discount_ids
        empty_result = {
            "show_global_discount": False,
            "global_discount_amount_currency": 0.0,
            "global_discount_amount": 0.0,
            "global_discount_amount_foreign": 0.0,
            "subtotal_gross_currency": base_amount_currency,
            "subtotal_gross": base_amount,
            "subtotal_gross_foreign": base_amount_foreign or 0.0,
            "global_discount_lines": [],
        }
        if not discounts:
            return empty_result

        subtotal_by_taxes = document._l10n_ve_global_discount_subtotal_by_taxes()
        global_discount_lines = document._l10n_ve_get_global_discount_lines_data(
            subtotal_by_taxes
        )
        global_discount_amount_currency = sum(
            line["amount"] for line in global_discount_lines
        )
        currency = document.currency_id
        if float_is_zero(
            global_discount_amount_currency,
            precision_rounding=currency.rounding,
        ):
            return empty_result

        rate = self._l10n_ve_get_document_currency_rate(document)
        company = document.company_id
        if currency == company.currency_id:
            global_discount_amount = global_discount_amount_currency
        else:
            global_discount_amount = company.currency_id.round(
                global_discount_amount_currency / rate
            )

        global_discount_amount_foreign = 0.0
        if document._name == "account.move":
            foreign_currency = getattr(document, "foreign_currency_id", False) or getattr(
                company, "foreign_currency_id", False
            )
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

        return {
            "show_global_discount": True,
            "global_discount_amount_currency": global_discount_amount_currency,
            "global_discount_amount": global_discount_amount,
            "global_discount_amount_foreign": global_discount_amount_foreign,
            "subtotal_gross_currency": base_amount_currency
            + global_discount_amount_currency,
            "subtotal_gross": base_amount + global_discount_amount,
            "subtotal_gross_foreign": (base_amount_foreign or 0.0)
            + global_discount_amount_foreign,
            "global_discount_lines": global_discount_lines,
        }

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

    def write(self, vals):
        """Impide modificar alícuotas fiscales venezolas ya configuradas.

        Notes
        -----
        Art. 13 num. 9-11 PA SNAT/2011/0071: porcentajes de IVA en facturas.
        """

        from odoo.exceptions import UserError

        ve_taxes = self.filtered(lambda t: t.country_code == "VE")
        if ve_taxes:
            if "amount" in vals:
                raise UserError(
                    self.env._(
                        "No está permitido modificar la alícuota de los "
                        "impuestos del país Venezuela."
                    )
                )
            if "name" in vals:
                raise UserError(
                    self.env._(
                        "No está permitido modificar el nombre de los "
                        "impuestos del país Venezuela."
                    )
                )
        return super().write(vals)
