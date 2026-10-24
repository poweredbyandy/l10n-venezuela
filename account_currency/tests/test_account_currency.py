# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import Form, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

# BCV-like document rate used by fractional / multi-product cases (foreign per company).
BCV_LIKE_RATE = 0.0011283789448551056


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
        sale_price_group = cls.env.ref(
            "pba_sale_price_group.group_pba_edit_sale_price",
            raise_if_not_found=False,
        )
        if sale_price_group:
            cls.env.user.write({"groups_id": [(4, sale_price_group.id)]})

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
        self.assertAlmostEqual(line.price_total_currency, 50.0)
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
        self.assertAlmostEqual(invoice.invoice_currency_rate, 2.0)
        self.assertAlmostEqual(line.price_subtotal, 143.15)
        self.assertAlmostEqual(line.price_subtotal_currency, 71.58, places=2)
        self.assertAlmostEqual(line.price_total_currency, 71.58, places=2)
        self.assertAlmostEqual(abs(line.balance), 71.58, places=2)
        self.assertAlmostEqual(abs(line.amount_currency), 143.15, places=2)
        self.assertAlmostEqual(line.price_unit_company_currency, 2.24, places=2)
        invoice.action_post()
        self.assertAlmostEqual(abs(line.balance), 71.58, places=2)
        self.assertAlmostEqual(abs(line.amount_currency), 143.15, places=2)
        self.assertAlmostEqual(line.price_subtotal_currency, 71.58, places=2)

    def test_company_currency_price_unit_ignores_discount(self):
        invoice = self._create_invoice()
        line = invoice.invoice_line_ids
        line.discount = 10.0
        self.assertAlmostEqual(line.price_subtotal_currency, 45.0)
        self.assertAlmostEqual(line.price_unit_company_currency, 50.0)
        self.assertAlmostEqual(line.price_total_currency, 45.0)

    def test_company_currency_subtotal_updates_before_save(self):
        invoice = self._create_invoice()
        with Form(invoice) as move_form:
            with move_form.invoice_line_ids.edit(0) as line_form:
                line_form.price_unit = 300.0
                self.assertAlmostEqual(line_form.price_subtotal_currency, 150.0)
                self.assertAlmostEqual(line_form.price_total_currency, 150.0)
                self.assertFalse(line_form.manually_price_subtotal_currency)
        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.price_subtotal_currency, 150.0)
        self.assertAlmostEqual(line.price_total_currency, 150.0)
        self.assertAlmostEqual(abs(line.balance), 150.0)
        self.assertFalse(line.manually_price_subtotal_currency)

    def test_manual_company_currency_subtotal(self):
        invoice = self._create_invoice()
        line = invoice.invoice_line_ids
        line.write(
            {
                "price_subtotal_currency": 40.0,
                "manually_price_subtotal_currency": True,
            }
        )
        self.assertAlmostEqual(line.currency_rate, 2.5)
        self.assertAlmostEqual(abs(line.balance), 40.0)
        self.assertAlmostEqual(line.price_total_currency, 40.0)
        self.assertTrue(line.warning_rate_difference)
        self.assertTrue(line.has_rate_difference)
        self.assertTrue(invoice.lines_with_rate_difference)

        line.reset_price_subtotal_currency()
        self.assertFalse(line.manually_price_subtotal_currency)
        self.assertAlmostEqual(line.currency_rate, 2.0)
        self.assertAlmostEqual(line.price_subtotal_currency, 50.0)
        self.assertAlmostEqual(line.price_total_currency, 50.0)
        self.assertFalse(line.warning_rate_difference)
        self.assertFalse(invoice.lines_with_rate_difference)

    def test_company_currency_subtotal_typed_in_form_is_manual(self):
        invoice = self._create_invoice()
        with Form(invoice) as move_form:
            with move_form.invoice_line_ids.edit(0) as line_form:
                line_form.price_subtotal_currency = 40.0
                self.assertTrue(line_form.manually_price_subtotal_currency)
        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.price_subtotal_currency, 40.0)
        self.assertAlmostEqual(line.currency_rate, 2.5)
        self.assertAlmostEqual(abs(line.balance), 40.0)

    def test_company_currency_total_typed_in_form_is_manual(self):
        tax = self._sale_percent_tax(16)
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
                            "name": "Taxed",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [(6, 0, tax.ids)],
                        },
                    )
                ],
            }
        )
        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.price_subtotal, 100.0)
        self.assertAlmostEqual(line.price_total, 116.0)
        self.assertAlmostEqual(line.price_subtotal_currency, 50.0)
        self.assertAlmostEqual(line.price_total_currency, 58.0)

        with Form(invoice) as move_form:
            with move_form.invoice_line_ids.edit(0) as line_form:
                line_form.price_total_currency = 46.4
                self.assertTrue(line_form.manually_price_subtotal_currency)
                self.assertAlmostEqual(line_form.price_subtotal_currency, 40.0)
        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.price_total_currency, 46.4)
        self.assertAlmostEqual(line.price_subtotal_currency, 40.0)
        self.assertAlmostEqual(line.currency_rate, 2.5)
        self.assertAlmostEqual(abs(line.balance), 40.0)

    def test_manual_subtotal_on_zero_amount_line_keeps_invoice_rate(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2024-01-10",
                "currency_id": self.foreign_currency.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Zero quantity",
                            "quantity": 0.0,
                            "price_unit": 100.0,
                            "tax_ids": [(6, 0, [])],
                            "price_subtotal_currency": 40.0,
                            "manually_price_subtotal_currency": True,
                        },
                    )
                ],
            }
        )
        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.currency_rate, 2.0)
        self.assertFalse(line.warning_rate_difference)
        line.write({"quantity": 1.0})
        self.assertAlmostEqual(line.currency_rate, 2.5)
        self.assertAlmostEqual(abs(line.balance), 40.0)

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

    def test_vendor_bill_document_rate_is_editable(self):
        bill = self._create_invoice(move_type="in_invoice")
        self.assertAlmostEqual(bill.invoice_currency_rate, 2.0)
        bill.invoice_currency_rate = 2.5
        self.assertAlmostEqual(bill.invoice_currency_rate, 2.5)
        self.assertAlmostEqual(bill.l10n_ve_inverse_rate, 0.4)
        line = bill.invoice_line_ids
        self.assertAlmostEqual(line.price_subtotal_currency, 40.0)
        self.assertAlmostEqual(abs(line.balance), 40.0)
        bill.l10n_ve_inverse_rate = 0.25
        self.assertAlmostEqual(bill.invoice_currency_rate, 4.0)
        self.assertAlmostEqual(bill.l10n_ve_inverse_rate, 0.25)
        self.assertAlmostEqual(line.price_subtotal_currency, 25.0)
        self.assertAlmostEqual(abs(line.balance), 25.0)

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
        # Document rate on 2026-10-20 is 4.0 (setup_other_currency).
        # Line A: 8.29 → company 2.07, total 2.40 (2.07 + round(2.07*16%)).
        # Line B: 8.86 → company 2.22, total 2.58.
        tax = self._sale_percent_tax(16)
        invoice = self._create_foreign_taxed_invoice(self.foreign_currency, tax)
        self.assertAlmostEqual(invoice.invoice_currency_rate, 4.0)
        by_name = {line.name: line for line in invoice.invoice_line_ids}
        line_a = by_name["Line A"]
        line_b = by_name["Line B"]
        self.assertFalse(line_a.manually_price_subtotal_currency)
        self.assertFalse(line_b.manually_price_subtotal_currency)
        self.assertAlmostEqual(line_a.currency_rate, 4.0, places=6)
        self.assertAlmostEqual(line_b.currency_rate, 4.0, places=6)
        self.assertAlmostEqual(line_a.price_subtotal_currency, 2.07, places=2)
        self.assertAlmostEqual(line_a.price_total_currency, 2.40, places=2)
        self.assertAlmostEqual(line_b.price_subtotal_currency, 2.22, places=2)
        self.assertAlmostEqual(line_b.price_total_currency, 2.58, places=2)
        self.assertAlmostEqual(abs(invoice.amount_untaxed_signed), 4.29, places=2)

        invoice.action_post()
        self.assertAlmostEqual(line_a.price_subtotal_currency, 2.07, places=2)
        self.assertAlmostEqual(line_a.price_total_currency, 2.40, places=2)
        self.assertAlmostEqual(line_b.price_subtotal_currency, 2.22, places=2)
        self.assertAlmostEqual(line_b.price_total_currency, 2.58, places=2)
        self.assertAlmostEqual(abs(line_a.balance), 2.07, places=2)
        self.assertAlmostEqual(abs(line_b.balance), 2.22, places=2)
        self.assertAlmostEqual(abs(invoice.amount_untaxed_signed), 4.29, places=2)
        # Without account_invoice_show_currency_rate, posted lines keep the
        # document rate (balances already reflect per-line rounding).
        self.assertAlmostEqual(line_a.currency_rate, 4.0, places=6)
        self.assertAlmostEqual(line_b.currency_rate, 4.0, places=6)
        self.assertAlmostEqual(
            abs(line_a.amount_currency) / abs(line_a.balance),
            4.004830917874396,
            places=6,
        )
        self.assertAlmostEqual(
            abs(line_b.amount_currency) / abs(line_b.balance),
            3.990990990990991,
            places=6,
        )

    def test_fractional_foreign_unit_matches_machine_bs_tax(self):
        """Many USD decimals: asiento = round(USD)/tasa and IVA on that Bs base.

        Reproduces INV/2026/02772: unit 1.43234234 at BCV_LIKE_RATE must not
        post company base from the unrounded unit (1269.38) while the fiscal
        machine prints base 1267.30, tax 202.77, total 1470.07.
        """
        self.env.company.tax_calculation_rounding_method = "round_globally"
        tax = self._sale_percent_tax(16)
        currency = self.setup_other_currency(
            "EUR",
            rates=[("2026-10-01", BCV_LIKE_RATE)],
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
        self.assertAlmostEqual(line.price_subtotal, 1.43, places=2)
        self.assertAlmostEqual(invoice.invoice_currency_rate, BCV_LIKE_RATE, places=12)
        self.assertAlmostEqual(line.price_subtotal_currency, 1267.30, places=2)
        self.assertAlmostEqual(line.price_total_currency, 1470.07, places=2)
        self.assertAlmostEqual(line.price_unit_company_currency, 1267.30, places=2)
        self.assertAlmostEqual(abs(line.balance), 1267.30, places=2)
        self.assertNotAlmostEqual(
            abs(line.balance),
            1269.38,
            places=2,
            msg="Must not post unrounded price_unit/rate",
        )
        self.assertAlmostEqual(abs(invoice.amount_untaxed_signed), 1267.30, places=2)
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), 202.77, places=2)
        self.assertAlmostEqual(abs(invoice.amount_total_signed), 1470.07, places=2)

        invoice.action_post()
        self.assertAlmostEqual(abs(line.balance), 1267.30, places=2)
        self.assertAlmostEqual(line.price_subtotal_currency, 1267.30, places=2)
        self.assertAlmostEqual(line.price_total_currency, 1470.07, places=2)
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), 202.77, places=2)
        self.assertAlmostEqual(abs(invoice.amount_total_signed), 1470.07, places=2)

    def _bcv_like_currency(self):
        self.env.company.tax_calculation_rounding_method = "round_globally"
        currency = self.setup_other_currency(
            "EUR",
            rates=[("2026-10-01", BCV_LIKE_RATE)],
        )
        self.assertNotEqual(currency, self.env.company.currency_id)
        return currency

    def _create_fractional_multi_tax_invoice(self, currency, line_specs):
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

    def _assert_lines_fixed_company_base(self, invoice, line_specs):
        product_lines = invoice.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        self.assertEqual(len(product_lines), len(line_specs))
        self.assertAlmostEqual(invoice.invoice_currency_rate, BCV_LIKE_RATE, places=12)
        for line, spec in zip(product_lines, line_specs, strict=True):
            self.assertEqual(line.name, spec["name"])
            self.assertAlmostEqual(line.price_subtotal, spec["foreign"], places=2)
            self.assertAlmostEqual(
                line.price_subtotal_currency, spec["base_company"], places=2
            )
            self.assertAlmostEqual(abs(line.balance), spec["base_company"], delta=0.02)
            if abs(spec["unrounded_base"] - spec["base_company"]) > 0.05:
                self.assertNotAlmostEqual(
                    abs(line.balance),
                    spec["unrounded_base"],
                    places=2,
                    msg=f"{spec['name']} must not use unrounded price_unit/rate",
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
                "foreign": 1.43,
                "base_company": 1267.30,
                "unrounded_base": 1269.38,
            },
            {
                "name": "Panel B",
                "price_unit": 2.55555555,
                "quantity": 3.0,
                "tax": tax16,
                "foreign": 7.67,
                "base_company": 6797.36,
                "unrounded_base": 6794.41,
            },
            {
                "name": "Panel C",
                "price_unit": 10.99999999,
                "quantity": 2.0,
                "discount": 10.0,
                "tax": tax16,
                "foreign": 19.80,
                "base_company": 17547.30,
                "unrounded_base": 17547.30,
            },
        ]
        invoice = self._create_fractional_multi_tax_invoice(currency, specs)
        self._assert_lines_fixed_company_base(invoice, specs)
        self.assertAlmostEqual(abs(invoice.amount_untaxed_signed), 25611.96, places=2)
        self.assertNotAlmostEqual(
            abs(invoice.amount_untaxed_signed), 25611.08, places=2
        )
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), 4097.91, places=2)
        self.assertAlmostEqual(abs(invoice.amount_total_signed), 29709.87, places=2)
        invoice.action_post()
        self.assertAlmostEqual(abs(invoice.amount_untaxed_signed), 25611.96, places=2)
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), 4097.91, places=2)
        self.assertAlmostEqual(abs(invoice.amount_total_signed), 29709.87, places=2)

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
                "foreign": 1.43,
                "base_company": 1267.30,
                "unrounded_base": 1269.38,
            },
            {
                "name": "IVA 8",
                "price_unit": 5.67890123,
                "quantity": 2.0,
                "tax": tax8,
                "foreign": 11.36,
                "base_company": 10067.54,
                "unrounded_base": 10065.59,
            },
            {
                "name": "Exento",
                "price_unit": 3.14159265,
                "quantity": 4.0,
                "tax": tax0,
                "foreign": 12.57,
                "base_company": 11139.87,
                "unrounded_base": 11136.66,
            },
            {
                "name": "IVA 16 qty",
                "price_unit": 0.99999999,
                "quantity": 7.0,
                "tax": tax16,
                "foreign": 7.0,
                "base_company": 6203.59,
                "unrounded_base": 6203.59,
            },
        ]
        invoice = self._create_fractional_multi_tax_invoice(currency, specs)
        self._assert_lines_fixed_company_base(invoice, specs)
        self.assertAlmostEqual(abs(invoice.amount_untaxed_signed), 28678.31, places=2)
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), 2000.74, places=2)
        self.assertAlmostEqual(abs(invoice.amount_total_signed), 30679.05, places=2)

        tax_lines = invoice.line_ids.filtered("tax_line_id")
        self.assertEqual(len(tax_lines), 2)
        tax_by_percent = {
            line.tax_line_id.amount: abs(line.balance) for line in tax_lines
        }
        self.assertAlmostEqual(tax_by_percent[16.0], 1195.34, places=2)
        self.assertAlmostEqual(tax_by_percent[8.0], 805.40, places=2)

        invoice.action_post()
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), 2000.74, places=2)
        self.assertAlmostEqual(abs(invoice.amount_total_signed), 30679.05, places=2)

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
                "foreign": 1.43,
                "base_company": 1267.30,
                "unrounded_base": 1269.38,
            },
            {
                "name": "B",
                "price_unit": 9.87654321,
                "quantity": 5.0,
                "tax": tax8,
                "foreign": 49.38,
                "base_company": 43761.89,
                "unrounded_base": 43764.30,
            },
        ]
        invoice = self._create_fractional_multi_tax_invoice(currency, specs)
        self._assert_lines_fixed_company_base(invoice, specs)
        self.assertAlmostEqual(abs(invoice.amount_untaxed_signed), 45029.20, places=2)
        self.assertNotAlmostEqual(
            abs(invoice.amount_untaxed_signed), 45033.68, places=2
        )
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), 3703.72, places=2)
        self.assertNotAlmostEqual(
            abs(invoice.amount_tax_signed),
            3704.24,
            places=2,
            msg="Tax must not be computed from unrounded foreign bases",
        )


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
