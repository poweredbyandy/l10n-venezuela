# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import fields
from odoo.tests import Form, tagged
from odoo.tools import float_round

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestAccountCurrency(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.write(
            {
                "account_fiscal_country_id": cls.env.ref("base.ve").id,
                "account_sale_tax_id": False,
                "account_purchase_tax_id": False,
            }
        )
        cls.foreign_currency = cls.setup_other_currency(
            "EUR", rates=[("2016-01-01", 2.0), ("2024-02-01", 4.0)]
        )

    def _create_invoice(self, move_type="out_invoice", invoice_date="2024-01-10"):
        return self.init_invoice(
            move_type,
            partner=self.partner_a,
            invoice_date=invoice_date,
            currency=self.foreign_currency,
            amounts=[100.0],
            taxes=self.env["account.tax"],
        )

    def test_invoice_rates(self):
        invoice = self._create_invoice()
        self.assertAlmostEqual(invoice.invoice_currency_rate, 2.0)
        self.assertAlmostEqual(invoice.l10n_ve_inverse_rate, 0.5)
        self.assertFalse(invoice.l10n_ve_currency_rate_outdated)

    def test_company_currency_line_amounts(self):
        invoice = self._create_invoice()
        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.price_subtotal_currency, 50.0)
        self.assertAlmostEqual(line.price_unit_company_currency, 50.0)
        self.assertAlmostEqual(invoice._l10n_ve_to_company_abs_amount(), 50.0)

    def test_company_currency_uses_native_subtotal(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2024-01-10",
                "currency_id": self.foreign_currency.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Fractional unit price",
                            "quantity": 32.0,
                            "price_unit": 4.473315,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        line = invoice.invoice_line_ids
        rate = invoice.invoice_currency_rate
        expected_company = invoice.company_currency_id.round(line.price_subtotal / rate)

        self.assertAlmostEqual(line.price_subtotal, 143.15)
        self.assertAlmostEqual(line.price_subtotal_currency, expected_company, places=2)
        self.assertAlmostEqual(abs(line.balance), expected_company, places=2)
        self.assertAlmostEqual(abs(line.amount_currency), line.price_subtotal, places=2)
        prec = self.env["decimal.precision"].precision_get("Product Price")
        self.assertAlmostEqual(
            line.price_unit_company_currency,
            float_round(expected_company / line.quantity, precision_digits=prec),
            places=prec,
        )
        invoice.action_post()
        self.assertAlmostEqual(abs(line.balance), expected_company, places=2)
        self.assertAlmostEqual(abs(line.amount_currency), line.price_subtotal, places=2)

    def test_company_currency_price_unit_ignores_discount(self):
        invoice = self._create_invoice()
        line = invoice.invoice_line_ids
        line.discount = 10.0
        self.assertAlmostEqual(line.price_subtotal_currency, 45.0)
        # Unit stays pre-discount so unit × qty × (1 - discount%) = subtotal.
        self.assertAlmostEqual(line.price_unit_company_currency, 50.0)
        self.assertAlmostEqual(
            line.price_unit_company_currency * line.quantity * 0.9,
            line.price_subtotal_currency,
            places=2,
        )


    def test_company_currency_subtotal_updates_before_save(self):
        invoice = self._create_invoice()
        with Form(invoice) as move_form:
            with move_form.invoice_line_ids.edit(0) as line_form:
                line_form.price_unit = 300.0
                self.assertAlmostEqual(line_form.price_subtotal_currency, 150.0)
        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.price_subtotal_currency, 150.0)
        self.assertAlmostEqual(abs(line.balance), 150.0)



    def test_tax_totals_in_company_currency(self):
        invoice = self._create_invoice()
        self.assertTrue(invoice.tax_totals["display_in_company_currency"])
        self.assertEqual(
            invoice.tax_totals["company_currency_id"],
            invoice.company_currency_id.id,
        )

    def test_outdated_rate_refresh(self):
        invoice = self._create_invoice()
        invoice.invoice_currency_rate = 3.0
        self.assertTrue(invoice.l10n_ve_currency_rate_outdated)
        invoice.refresh_invoice_currency_rate()
        self.assertAlmostEqual(invoice.invoice_currency_rate, 2.0)
        self.assertFalse(invoice.l10n_ve_currency_rate_outdated)

    def test_refund_keeps_origin_rate(self):
        invoice = self._create_invoice()
        invoice.action_post()
        refund = invoice._reverse_moves(
            default_values_list=[{"invoice_date": fields.Date.to_date("2024-02-10")}]
        )
        self.assertAlmostEqual(refund.invoice_currency_rate, 2.0)
        refund.refresh_invoice_currency_rate()
        self.assertAlmostEqual(refund.invoice_currency_rate, 2.0)


    def _sale_percent_tax(self, amount):
        country = self.env.company.account_fiscal_country_id
        tax_group = self.env["account.tax.group"].create(
            {
                "name": "Test IVA",
                "company_id": self.env.company.id,
                "country_id": country.id,
            }
        )
        return self.percent_tax(
            amount,
            type_tax_use="sale",
            tax_group_id=tax_group.id,
            country_id=country.id,
        )

    def _create_foreign_taxed_invoice(self, currency, tax):
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-10-20",
                "date": "2026-10-20",
                "currency_id": currency.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Line A",
                            "quantity": 1.0,
                            "price_unit": 8.29,
                            "tax_ids": [(6, 0, tax.ids)],
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "name": "Line B",
                            "quantity": 1.0,
                            "price_unit": 8.86,
                            "tax_ids": [(6, 0, tax.ids)],
                        },
                    ),
                ],
            }
        )

    def test_foreign_tax_company_amounts_are_native(self):
        tax = self._sale_percent_tax(16)
        invoice = self._create_foreign_taxed_invoice(self.foreign_currency, tax)
        invoice.action_post()
        self.assertAlmostEqual(
            invoice.tax_totals["base_amount"],
            abs(invoice.amount_untaxed_signed),
            places=2,
        )
        self.assertAlmostEqual(
            invoice.tax_totals["tax_amount"],
            abs(invoice.amount_tax_signed),
            places=2,
        )
        self.assertAlmostEqual(
            invoice.tax_totals["total_amount"],
            abs(invoice.amount_total_signed),
            places=2,
        )
        for line in invoice.invoice_line_ids:
            self.assertAlmostEqual(
                line.price_subtotal_currency, abs(line.balance), places=2
            )
            self.assertAlmostEqual(
                line.currency_rate, invoice.invoice_currency_rate, places=6
            )

    def test_fractional_foreign_unit_matches_machine_bs_tax(self):
        """Many USD decimals: asiento = round(USD)/tasa and IVA on that Bs base.

        Reproduces INV/2026/02772: unit 1.43234234 at rate ~0.00112838 must not
        post company base from the unrounded unit (1269.38) while the fiscal
        machine prints round(1.43/rate)=1267.30 and tax round(1267.30*16%,2).
        """
        # Same as TFHKA / VE production: convert raw foreign tax via rate, then
        # round company amounts (not round foreign tax before conversion).
        self.env.company.tax_calculation_rounding_method = "round_globally"
        tax = self._sale_percent_tax(16)
        # Company currency is typically USD in tests; use another currency as
        # document currency with a BCV-like rate (foreign per company).
        currency = self.setup_other_currency(
            "EUR",
            rates=[("2026-10-01", 0.0011283789448551056)],
        )
        self.assertNotEqual(currency, self.env.company.currency_id)
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-10-23",
                "date": "2026-10-23",
                "currency_id": currency.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Fractional foreign unit",
                            "quantity": 1.0,
                            "price_unit": 1.43234234,
                            "tax_ids": [(6, 0, tax.ids)],
                        },
                    )
                ],
            }
        )
        line = invoice.invoice_line_ids
        rate = invoice.invoice_currency_rate
        company_currency = invoice.company_currency_id
        foreign_subtotal = currency.round(line.price_unit)
        expected_base = company_currency.round(foreign_subtotal / rate)
        expected_tax = company_currency.round(foreign_subtotal * 0.16 / rate)
        expected_total = company_currency.round(expected_base + expected_tax)
        unrounded_company_base = company_currency.round(line.price_unit / rate)

        self.assertAlmostEqual(line.price_subtotal, 1.43, places=2)
        self.assertAlmostEqual(rate, 0.0011283789448551056, places=12)
        self.assertAlmostEqual(expected_base, 1267.30, places=2)
        self.assertAlmostEqual(expected_tax, 202.77, places=2)
        self.assertAlmostEqual(expected_total, 1470.07, places=2)
        self.assertAlmostEqual(unrounded_company_base, 1269.38, places=2)
        self.assertNotAlmostEqual(
            abs(line.balance),
            unrounded_company_base,
            places=2,
            msg="Must not post unrounded price_unit/rate (machine uses round(USD)/rate)",
        )
        self.assertAlmostEqual(line.price_subtotal_currency, expected_base, places=2)
        self.assertAlmostEqual(line.price_unit_company_currency, expected_base, places=2)
        self.assertAlmostEqual(abs(line.balance), expected_base, places=2)
        self.assertAlmostEqual(abs(invoice.amount_untaxed_signed), expected_base, places=2)
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected_tax, places=2)
        self.assertAlmostEqual(abs(invoice.amount_total_signed), expected_total, places=2)

        invoice.action_post()
        self.assertAlmostEqual(abs(line.balance), expected_base, places=2)
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected_tax, places=2)
        self.assertAlmostEqual(abs(invoice.amount_total_signed), expected_total, places=2)

    def _bcv_like_currency(self):
        """Foreign currency with a BCV-like rate (foreign units per company unit)."""
        self.env.company.tax_calculation_rounding_method = "round_globally"
        currency = self.setup_other_currency(
            "EUR",
            rates=[("2026-10-01", 0.0011283789448551056)],
        )
        self.assertNotEqual(currency, self.env.company.currency_id)
        return currency

    def _machine_line_company_amounts(
        self, currency, company_currency, rate, price_unit, quantity=1.0, discount=0.0
    ):
        """Per-line amounts as TFHKA: round(foreign) then / rate."""
        foreign = currency.round(
            (price_unit or 0.0)
            * (quantity or 0.0)
            * (1.0 - (discount or 0.0) / 100.0)
        )
        base_company = company_currency.round(foreign / rate)
        return foreign, base_company

    def _expected_invoice_company_totals(self, currency, company_currency, rate, lines):
        """Aggregate expected base/tax/total with rounded foreign bases.

        ``lines``: iterable of dicts with price_unit, quantity, discount, tax_percent.
        Tax company amount follows round_globally: sum(raw foreign tax / rate)
        per tax percent, then round once (Odoo after rounded price_unit).
        """
        raw_base_company = 0.0
        raw_tax_company_by_percent = defaultdict(float)
        raw_unrounded_base = 0.0
        for spec in lines:
            price_unit = spec["price_unit"]
            quantity = spec.get("quantity", 1.0)
            discount = spec.get("discount", 0.0)
            tax_percent = spec.get("tax_percent") or 0.0
            foreign, _base_company = self._machine_line_company_amounts(
                currency,
                company_currency,
                rate,
                price_unit,
                quantity=quantity,
                discount=discount,
            )
            raw_base_company += foreign / rate
            raw_unrounded_base += (
                price_unit * quantity * (1.0 - discount / 100.0) / rate
            )
            if tax_percent:
                raw_tax_company_by_percent[tax_percent] += (
                    foreign * tax_percent / 100.0
                ) / rate
        base_total = company_currency.round(raw_base_company)
        unrounded_base_total = company_currency.round(raw_unrounded_base)
        tax_total = 0.0
        tax_by_percent = {}
        for percent, raw_tax_company in raw_tax_company_by_percent.items():
            rounded_tax = company_currency.round(raw_tax_company)
            tax_by_percent[percent] = rounded_tax
            tax_total = company_currency.round(tax_total + rounded_tax)
        total = company_currency.round(base_total + tax_total)
        return {
            "base": base_total,
            "tax": tax_total,
            "total": total,
            "unrounded_base": unrounded_base_total,
            "tax_by_percent": tax_by_percent,
        }

    def _create_fractional_multi_tax_invoice(self, currency, line_specs):
        """Create out_invoice from line specs ``{name, price_unit, quantity, discount, tax}``."""
        invoice_lines = []
        for spec in line_specs:
            invoice_lines.append(
                (
                    0,
                    0,
                    {
                        "name": spec["name"],
                        "quantity": spec.get("quantity", 1.0),
                        "price_unit": spec["price_unit"],
                        "discount": spec.get("discount", 0.0),
                        "tax_ids": [(6, 0, spec["tax"].ids)] if spec.get("tax") else [],
                    },
                )
            )
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-10-23",
                "date": "2026-10-23",
                "currency_id": currency.id,
                "invoice_line_ids": invoice_lines,
            }
        )

    def _assert_lines_match_machine_base(self, invoice, line_specs):
        currency = invoice.currency_id
        company_currency = invoice.company_currency_id
        rate = invoice.invoice_currency_rate
        product_lines = invoice.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        self.assertEqual(len(product_lines), len(line_specs))
        for line, spec in zip(product_lines, line_specs):
            foreign, base_company = self._machine_line_company_amounts(
                currency,
                company_currency,
                rate,
                spec["price_unit"],
                quantity=spec.get("quantity", 1.0),
                discount=spec.get("discount", 0.0),
            )
            unrounded = company_currency.round(
                spec["price_unit"]
                * spec.get("quantity", 1.0)
                * (1.0 - spec.get("discount", 0.0) / 100.0)
                / rate
            )
            self.assertAlmostEqual(line.price_subtotal, foreign, places=2)
            # round_globally may park a ±0.01 delta on one base line.
            self.assertAlmostEqual(abs(line.balance), base_company, delta=0.01)
            self.assertAlmostEqual(
                line.price_subtotal_currency, base_company, places=2
            )
            if abs(unrounded - base_company) > 0.05:
                self.assertNotAlmostEqual(
                    abs(line.balance),
                    unrounded,
                    places=2,
                    msg="%s must not use unrounded price_unit/rate" % spec["name"],
                )
        self.assertAlmostEqual(
            abs(sum(product_lines.mapped("balance"))),
            abs(invoice.amount_untaxed_signed),
            places=2,
        )

    def test_multi_product_same_tax_fractional_units(self):
        """Several lines @16% with fractional USD units follow machine Bs bases."""
        currency = self._bcv_like_currency()
        tax16 = self._sale_percent_tax(16)
        specs = [
            {
                "name": "Panel A",
                "price_unit": 1.43234234,
                "quantity": 1.0,
                "tax": tax16,
                "tax_percent": 16.0,
            },
            {
                "name": "Panel B",
                "price_unit": 2.55555555,
                "quantity": 3.0,
                "tax": tax16,
                "tax_percent": 16.0,
            },
            {
                "name": "Panel C",
                "price_unit": 10.99999999,
                "quantity": 2.0,
                "discount": 10.0,
                "tax": tax16,
                "tax_percent": 16.0,
            },
        ]
        invoice = self._create_fractional_multi_tax_invoice(currency, specs)
        expected = self._expected_invoice_company_totals(
            currency,
            invoice.company_currency_id,
            invoice.invoice_currency_rate,
            specs,
        )
        self._assert_lines_match_machine_base(invoice, specs)
        self.assertNotAlmostEqual(
            abs(invoice.amount_untaxed_signed),
            expected["unrounded_base"],
            places=2,
        )
        self.assertAlmostEqual(
            abs(invoice.amount_untaxed_signed), expected["base"], places=2
        )
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected["tax"], places=2)
        self.assertAlmostEqual(
            abs(invoice.amount_total_signed), expected["total"], places=2
        )
        invoice.action_post()
        self.assertAlmostEqual(
            abs(invoice.amount_untaxed_signed), expected["base"], places=2
        )
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected["tax"], places=2)
        self.assertAlmostEqual(
            abs(invoice.amount_total_signed), expected["total"], places=2
        )

    def test_multi_product_mixed_tax_rates_fractional_units(self):
        """Lines with 16%, 8% and exempt keep per-line Bs base and tax buckets."""
        currency = self._bcv_like_currency()
        tax16 = self._sale_percent_tax(16)
        tax8 = self._sale_percent_tax(8)
        tax0 = self._sale_percent_tax(0)
        specs = [
            {
                "name": "IVA 16",
                "price_unit": 1.43234234,
                "quantity": 1.0,
                "tax": tax16,
                "tax_percent": 16.0,
            },
            {
                "name": "IVA 8",
                "price_unit": 5.67890123,
                "quantity": 2.0,
                "tax": tax8,
                "tax_percent": 8.0,
            },
            {
                "name": "Exento",
                "price_unit": 3.14159265,
                "quantity": 4.0,
                "tax": tax0,
                "tax_percent": 0.0,
            },
            {
                "name": "IVA 16 qty",
                "price_unit": 0.99999999,
                "quantity": 7.0,
                "tax": tax16,
                "tax_percent": 16.0,
            },
        ]
        invoice = self._create_fractional_multi_tax_invoice(currency, specs)
        expected = self._expected_invoice_company_totals(
            currency,
            invoice.company_currency_id,
            invoice.invoice_currency_rate,
            specs,
        )
        self._assert_lines_match_machine_base(invoice, specs)
        self.assertAlmostEqual(
            abs(invoice.amount_untaxed_signed), expected["base"], places=2
        )
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected["tax"], places=2)
        self.assertAlmostEqual(
            abs(invoice.amount_total_signed), expected["total"], places=2
        )

        tax_lines = invoice.line_ids.filtered("tax_line_id")
        self.assertEqual(len(tax_lines), 2)
        tax_by_percent = {
            line.tax_line_id.amount: abs(line.balance) for line in tax_lines
        }
        self.assertAlmostEqual(
            tax_by_percent[16.0], expected["tax_by_percent"][16.0], places=2
        )
        self.assertAlmostEqual(
            tax_by_percent[8.0], expected["tax_by_percent"][8.0], places=2
        )
        self.assertAlmostEqual(
            invoice.company_currency_id.round(
                tax_by_percent[16.0] + tax_by_percent[8.0]
            ),
            expected["tax"],
            places=2,
        )

        invoice.action_post()
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected["tax"], places=2)
        self.assertAlmostEqual(
            abs(invoice.amount_total_signed), expected["total"], places=2
        )

    def test_multi_product_mixed_taxes_reject_unrounded_company_base(self):
        """Guard: mixed taxes must not silently fall back to price_unit/rate."""
        currency = self._bcv_like_currency()
        tax16 = self._sale_percent_tax(16)
        tax8 = self._sale_percent_tax(8)
        specs = [
            {
                "name": "A",
                "price_unit": 1.43234234,
                "quantity": 1.0,
                "tax": tax16,
                "tax_percent": 16.0,
            },
            {
                "name": "B",
                "price_unit": 9.87654321,
                "quantity": 5.0,
                "tax": tax8,
                "tax_percent": 8.0,
            },
        ]
        invoice = self._create_fractional_multi_tax_invoice(currency, specs)
        expected = self._expected_invoice_company_totals(
            currency,
            invoice.company_currency_id,
            invoice.invoice_currency_rate,
            specs,
        )
        self.assertGreater(abs(expected["unrounded_base"] - expected["base"]), 0.009)
        self.assertAlmostEqual(
            abs(invoice.amount_untaxed_signed), expected["base"], places=2
        )
        self.assertNotAlmostEqual(
            abs(invoice.amount_untaxed_signed),
            expected["unrounded_base"],
            places=2,
        )
        wrong_tax = invoice.company_currency_id.round(
            (
                1.43234234 * 0.16
                + 9.87654321 * 5.0 * 0.08
            )
            / invoice.invoice_currency_rate
        )
        self.assertNotAlmostEqual(
            abs(invoice.amount_tax_signed),
            wrong_tax,
            places=2,
            msg="Tax must not be computed from unrounded foreign bases",
        )
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected["tax"], places=2)


@tagged("post_install", "-at_install")
class TestResCurrencyRate(AccountTestInvoicingCommon):
    def test_rate_change_is_tracked(self):
        currency = self.setup_other_currency("EUR", rates=[])
        rates = self.env["res.currency.rate"].with_context(
            tracking_disable=False, mail_notrack=False
        )
        rate = rates.create(
            {
                "currency_id": currency.id,
                "name": fields.Date.context_today(self.env.user),
                "rate": 2.0,
                "company_id": self.env.company.id,
            }
        )
        self.env.flush_all()
        self.env.cr.flush()
        rate.rate = 3.0
        self.env.flush_all()
        self.env.cr.flush()
        tracking = self.env["mail.tracking.value"].search(
            [
                ("mail_message_id.model", "=", "res.currency.rate"),
                ("mail_message_id.res_id", "=", rate.id),
                ("field_id.name", "=", "rate"),
            ]
        )
        self.assertEqual(tracking.old_value_float, 2.0)
        self.assertEqual(tracking.new_value_float, 3.0)
