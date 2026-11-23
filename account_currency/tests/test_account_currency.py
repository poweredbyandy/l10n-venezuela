# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import Form, tagged
from odoo.tools import float_round

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
            cls.env.user.write({"group_ids": [(4, sale_price_group.id)]})

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
        # Native Bs math: pu_bs = round(4.473315 / 2, Product Price) * 32
        self.assertAlmostEqual(line.price_subtotal_currency, 71.68, places=2)
        self.assertAlmostEqual(line.price_total_currency, 71.68, places=2)
        self.assertAlmostEqual(abs(line.balance), 71.68, places=2)
        self.assertAlmostEqual(abs(line.amount_currency), 143.15, places=2)
        self.assertAlmostEqual(line.price_unit_company_currency, 2.24, places=2)
        invoice.action_post()
        self.assertAlmostEqual(abs(line.balance), 71.68, places=2)
        self.assertAlmostEqual(abs(line.amount_currency), 143.15, places=2)
        self.assertAlmostEqual(line.price_subtotal_currency, 71.68, places=2)

    def test_company_currency_price_unit_ignores_discount(self):
        # Vendor bill: customer invoices may forbid per-line discount in this DB.
        invoice = self._create_invoice(move_type="in_invoice")
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

    def test_posted_manual_rate_does_not_rewrite_balance(self):
        bill = self._create_invoice(move_type="in_invoice")
        line = bill.invoice_line_ids
        line.write(
            {
                "price_subtotal_currency": 40.0,
                "manually_price_subtotal_currency": True,
            }
        )
        bill.action_post()
        stored_balance = line.balance
        self.env.cr.execute(
            "UPDATE account_move_line SET balance = %s WHERE id = %s",
            (stored_balance + 15.0, line.id),
        )
        line.invalidate_recordset()
        self.assertAlmostEqual(line.currency_rate, 2.5)
        self.assertAlmostEqual(line.balance, stored_balance + 15.0)

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

    def test_partial_refund_quantity_scales_company_amount(self):
        """Lowering the credited quantity must scale Bs and must not go red.

        The form save resends the previous company total. That leftover is not
        a manual rate.
        """
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
                            "name": "Bebida de Aloe sabor Coco",
                            "quantity": 3.0,
                            "price_unit": 40.0,
                            "discount": 8.0,
                            "tax_ids": [(6, 0, tax.ids)],
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        refund = invoice._reverse_moves(
            default_values_list=[{"invoice_date": fields.Date.to_date("2024-01-10")}]
        )
        origin = invoice.invoice_line_ids
        line = refund.invoice_line_ids
        stale_subtotal = line.price_subtotal_currency
        stale_total = line.price_total_currency
        self.assertAlmostEqual(stale_subtotal, origin.price_subtotal_currency)
        line.write(
            {
                "quantity": 1.0,
                "price_subtotal_currency": stale_subtotal,
                "price_total_currency": stale_total,
            }
        )
        company = line.company_currency_id
        expected_base = company.round(abs(origin.balance) / 3.0)
        self.assertAlmostEqual(line.price_subtotal, 36.80, places=2)
        self.assertFalse(line.manually_price_subtotal_currency)
        self.assertFalse(line.warning_rate_difference)
        self.assertAlmostEqual(line.price_subtotal_currency, expected_base, places=2)
        self.assertAlmostEqual(abs(line.balance), expected_base, places=2)
        self.assertLess(line.price_total_currency, stale_total)
        with Form(refund) as refund_form:
            with refund_form.invoice_line_ids.edit(0) as line_form:
                line_form.quantity = 2
                self.assertFalse(line_form.warning_rate_difference)
                self.assertFalse(line_form.manually_price_subtotal_currency)
                self.assertAlmostEqual(
                    line_form.price_subtotal_currency,
                    company.round(abs(origin.balance) * 2.0 / 3.0),
                    places=2,
                )
        line = refund.invoice_line_ids
        self.assertFalse(line.warning_rate_difference)
        self.assertAlmostEqual(
            line.price_subtotal_currency,
            company.round(abs(origin.balance) * 2.0 / 3.0),
            places=2,
        )
        self.assertAlmostEqual(
            abs(line.balance),
            company.round(abs(origin.balance) * 2.0 / 3.0),
            places=2,
        )

    def _sale_percent_tax(self, amount, **kwargs):
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
            type_tax_use=kwargs.pop("type_tax_use", "sale"),
            tax_group_id=tax_group.id,
            country_id=country.id,
            **kwargs,
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

    def _company_base_from_foreign_unit(self, price_unit, quantity=1.0, discount=0.0):
        """Expected Bs base under pu_bs = round(pu_foreign / rate, Product Price)."""
        prec = self.env["decimal.precision"].precision_get("Product Price")
        company_pu = float_round(price_unit / BCV_LIKE_RATE, precision_digits=prec)
        return self.env.company.currency_id.round(
            company_pu * quantity * (1.0 - discount / 100.0)
        )

    def test_fractional_foreign_unit_matches_machine_bs_tax(self):
        """Many USD decimals: asiento uses pu_bs = round(pu / rate) then qty.

        Fiscal print and journal share the same company unit so a VES document
        with that unit price matches the USD invoice company amounts.
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
        expected_base = self._company_base_from_foreign_unit(1.43234234)
        expected_tax = self.env.company.currency_id.round(expected_base * 0.16)
        expected_total = self.env.company.currency_id.round(
            expected_base + expected_tax
        )
        self.assertAlmostEqual(line.price_subtotal, 1.43, places=2)
        self.assertAlmostEqual(invoice.invoice_currency_rate, BCV_LIKE_RATE, places=12)
        self.assertAlmostEqual(line.price_subtotal_currency, expected_base, places=2)
        self.assertAlmostEqual(line.price_total_currency, expected_total, places=2)
        self.assertAlmostEqual(
            line.price_unit_company_currency, expected_base, places=2
        )
        self.assertAlmostEqual(abs(line.balance), expected_base, places=2)
        self.assertAlmostEqual(
            abs(invoice.amount_untaxed_signed), expected_base, places=2
        )
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected_tax, places=2)
        self.assertAlmostEqual(
            abs(invoice.amount_total_signed), expected_total, places=2
        )

        invoice.action_post()
        self.assertAlmostEqual(abs(line.balance), expected_base, places=2)
        self.assertAlmostEqual(line.price_subtotal_currency, expected_base, places=2)
        self.assertAlmostEqual(line.price_total_currency, expected_total, places=2)
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected_tax, places=2)
        self.assertAlmostEqual(
            abs(invoice.amount_total_signed), expected_total, places=2
        )

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
        company = self.env.company.currency_id
        expected_bases = []
        for line, spec in zip(product_lines, line_specs, strict=True):
            self.assertEqual(line.name, spec["name"])
            self.assertAlmostEqual(line.price_subtotal, spec["foreign"], places=2)
            expected_base = self._company_base_from_foreign_unit(
                spec["price_unit"],
                quantity=spec.get("quantity", 1.0),
                discount=spec.get("discount", 0.0),
            )
            expected_bases.append(expected_base)
            self.assertAlmostEqual(
                line.price_subtotal_currency, expected_base, places=2
            )
            self.assertAlmostEqual(abs(line.balance), expected_base, places=2)
        self.assertAlmostEqual(
            company.round(sum(product_lines.mapped("price_subtotal_currency"))),
            company.round(sum(expected_bases)),
            places=2,
        )

    def test_multi_product_same_tax_fractional_units(self):
        """Several lines @16% with fractional USD units follow pu_bs bases."""
        currency = self._bcv_like_currency()
        tax16 = self._sale_percent_tax(16)
        specs = [
            {
                "name": "Panel A",
                "price_unit": 1.43234234,
                "quantity": 1.0,
                "tax": tax16,
                "foreign": 1.43,
            },
            {
                "name": "Panel B",
                "price_unit": 2.55555555,
                "quantity": 3.0,
                "tax": tax16,
                "foreign": 7.67,
            },
            {
                "name": "Panel C",
                "price_unit": 10.99999999,
                "quantity": 2.0,
                "tax": tax16,
                "foreign": 22.0,
            },
        ]
        invoice = self._create_fractional_multi_tax_invoice(currency, specs)
        self._assert_lines_fixed_company_base(invoice, specs)
        company = self.env.company.currency_id
        expected_untaxed = company.round(
            sum(
                self._company_base_from_foreign_unit(
                    spec["price_unit"],
                    quantity=spec.get("quantity", 1.0),
                    discount=spec.get("discount", 0.0),
                )
                for spec in specs
            )
        )
        expected_tax = company.round(expected_untaxed * 0.16)
        expected_total = company.round(expected_untaxed + expected_tax)
        self.assertAlmostEqual(
            abs(invoice.amount_untaxed_signed), expected_untaxed, places=2
        )
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected_tax, places=2)
        self.assertAlmostEqual(
            abs(invoice.amount_total_signed), expected_total, places=2
        )
        invoice.action_post()
        self.assertAlmostEqual(
            abs(invoice.amount_untaxed_signed), expected_untaxed, places=2
        )
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected_tax, places=2)
        self.assertAlmostEqual(
            abs(invoice.amount_total_signed), expected_total, places=2
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
                "foreign": 1.43,
            },
            {
                "name": "IVA 8",
                "price_unit": 5.67890123,
                "quantity": 2.0,
                "tax": tax8,
                "foreign": 11.36,
            },
            {
                "name": "Exento",
                "price_unit": 3.14159265,
                "quantity": 4.0,
                "tax": tax0,
                "foreign": 12.57,
            },
            {
                "name": "IVA 16 qty",
                "price_unit": 0.99999999,
                "quantity": 7.0,
                "tax": tax16,
                "foreign": 7.0,
            },
        ]
        invoice = self._create_fractional_multi_tax_invoice(currency, specs)
        self._assert_lines_fixed_company_base(invoice, specs)
        company = self.env.company.currency_id
        product_lines = invoice.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        base_by_rate = {16.0: 0.0, 8.0: 0.0, 0.0: 0.0}
        for line, spec in zip(product_lines, specs, strict=True):
            base_by_rate[spec["tax"].amount] = company.round(
                base_by_rate[spec["tax"].amount] + line.price_subtotal_currency
            )
        expected_untaxed = company.round(
            sum(product_lines.mapped("price_subtotal_currency"))
        )
        expected_tax16 = company.round(base_by_rate[16.0] * 0.16)
        expected_tax8 = company.round(base_by_rate[8.0] * 0.08)
        expected_tax = company.round(expected_tax16 + expected_tax8)
        expected_total = company.round(expected_untaxed + expected_tax)
        self.assertAlmostEqual(
            abs(invoice.amount_untaxed_signed), expected_untaxed, places=2
        )
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected_tax, places=2)
        self.assertAlmostEqual(
            abs(invoice.amount_total_signed), expected_total, places=2
        )

        tax_lines = invoice.line_ids.filtered("tax_line_id")
        self.assertEqual(len(tax_lines), 2)
        tax_by_percent = {
            line.tax_line_id.amount: abs(line.balance) for line in tax_lines
        }
        self.assertAlmostEqual(tax_by_percent[16.0], expected_tax16, places=2)
        self.assertAlmostEqual(tax_by_percent[8.0], expected_tax8, places=2)

        invoice.action_post()
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected_tax, places=2)
        self.assertAlmostEqual(
            abs(invoice.amount_total_signed), expected_total, places=2
        )

    def test_multi_product_mixed_taxes_reject_unrounded_company_base(self):
        """Guard: mixed taxes follow pu_bs company bases, not foreign/rate alone."""
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
            },
            {
                "name": "B",
                "price_unit": 9.87654321,
                "quantity": 5.0,
                "tax": tax8,
                "foreign": 49.38,
            },
        ]
        invoice = self._create_fractional_multi_tax_invoice(currency, specs)
        self._assert_lines_fixed_company_base(invoice, specs)
        expected_untaxed = sum(
            self._company_base_from_foreign_unit(
                spec["price_unit"],
                quantity=spec.get("quantity", 1.0),
            )
            for spec in specs
        )
        expected_tax = self.env.company.currency_id.round(
            self._company_base_from_foreign_unit(1.43234234) * 0.16
            + self._company_base_from_foreign_unit(9.87654321, quantity=5.0) * 0.08
        )
        self.assertAlmostEqual(
            abs(invoice.amount_untaxed_signed), expected_untaxed, places=2
        )
        self.assertAlmostEqual(abs(invoice.amount_tax_signed), expected_tax, places=2)

    def _invoice_rate_change_tax(self, price_unit, quantity):
        self.env.company.tax_calculation_rounding_method = "round_globally"
        precision = self.env["decimal.precision"].search(
            [("name", "=", "Product Price")], limit=1
        )
        if precision:
            precision.digits = 4
        tax = self._sale_percent_tax(16)
        self.setup_other_currency("EUR", rates=[("2026-10-01", 0.01)])
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": "2026-10-23",
                "date": "2026-10-23",
                "currency_id": self.foreign_currency.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Rate change",
                            "quantity": quantity,
                            "price_unit": price_unit,
                            "tax_ids": [(6, 0, tax.ids)],
                        },
                    )
                ],
            }
        )
        foreign_tax = invoice.amount_tax
        invoice.invoice_currency_rate = 0.0011259761227755357
        company = self.env.company.currency_id
        return invoice, foreign_tax, company

    def test_rate_change_fractional_unit_keeps_tax_percent_of_company_base(self):
        """Extra price decimals: Bs IVA stays 16% of the Bs base after a rate write.

        ``round(usd_tax / rate)`` is a different amount. Posted invoices are
        left untouched; only a later rate write on a draft takes this path.
        """
        invoice, foreign_tax, company = self._invoice_rate_change_tax(6.28595, 8.0)
        base = abs(invoice.amount_untaxed_signed)
        tax_amount = abs(invoice.amount_tax_signed)
        expected = company.round(base * 0.16)
        converted = company.round(invoice.amount_tax / invoice.invoice_currency_rate)
        self.assertAlmostEqual(invoice.amount_tax, foreign_tax, places=2)
        self.assertAlmostEqual(tax_amount, expected, places=2)
        self.assertNotAlmostEqual(expected, converted, places=2)

    def test_rate_change_even_price_company_tax_matches_both_formulas(self):
        """Prices that divide evenly already match. A rate write must not move them."""
        invoice, foreign_tax, company = self._invoice_rate_change_tax(15.0, 4.0)
        base = abs(invoice.amount_untaxed_signed)
        tax_amount = abs(invoice.amount_tax_signed)
        expected = company.round(base * 0.16)
        converted = company.round(invoice.amount_tax / invoice.invoice_currency_rate)
        self.assertAlmostEqual(invoice.amount_tax, foreign_tax, places=2)
        self.assertAlmostEqual(tax_amount, expected, places=2)
        self.assertAlmostEqual(tax_amount, converted, places=2)

    def _included_percent_tax(self, amount, type_tax_use="sale"):
        tax = self._sale_percent_tax(
            amount,
            type_tax_use=type_tax_use,
            price_include_override="tax_included",
        )
        self.assertTrue(tax.price_include)
        return tax

    def _create_taxed_move(
        self,
        currency,
        tax,
        price_unit,
        quantity=1.0,
        discount=0.0,
        invoice_date="2024-01-10",
        move_type="out_invoice",
    ):
        return self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner_a.id,
                "invoice_date": invoice_date,
                "date": invoice_date,
                "currency_id": currency.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Included tax line",
                            "quantity": quantity,
                            "price_unit": price_unit,
                            "discount": discount,
                            "tax_ids": [(6, 0, tax.ids)],
                        },
                    )
                ],
            }
        )

    def _assert_included_matches_native_company_invoice(
        self,
        foreign,
        price_unit,
        quantity=1.0,
        discount=0.0,
        invoice_date="2024-01-10",
        move_type="out_invoice",
    ):
        """Company amounts of a price-included tax follow a native company invoice.

        The foreign unit is converted with the same rounding as an excluded tax
        (``round(pu / rate, Product Price)``). That company unit, with the same
        included tax, is the expected base, tax and total.
        """
        line = foreign.invoice_line_ids
        company_pu = foreign._l10n_ve_company_price_unit_from_foreign_unit(price_unit)
        native = self._create_taxed_move(
            self.env.company.currency_id,
            line.tax_ids,
            company_pu,
            quantity=quantity,
            discount=discount,
            invoice_date=invoice_date,
            move_type=move_type,
        )
        native_line = native.invoice_line_ids
        company = self.env.company.currency_id
        pairs = {
            "subtotal_currency": (line.price_subtotal_currency, native_line.price_subtotal),
            "total_currency": (line.price_total_currency, native_line.price_total),
            "balance": (abs(line.balance), abs(native_line.balance)),
            "untaxed_signed": (
                abs(foreign.amount_untaxed_signed),
                abs(native.amount_untaxed_signed),
            ),
            "tax_signed": (
                abs(foreign.amount_tax_signed),
                abs(native.amount_tax_signed),
            ),
            "total_signed": (
                abs(foreign.amount_total_signed),
                abs(native.amount_total_signed),
            ),
        }
        mismatches = {
            key: (company.round(got), company.round(expected))
            for key, (got, expected) in pairs.items()
            if company.compare_amounts(got, expected)
        }
        self.assertFalse(
            mismatches,
            "Included tax diverges from a company-currency invoice at unit %s. "
            "Foreign price_subtotal=%s price_total=%s unit_company=%s. "
            "Native price_subtotal=%s price_total=%s. Mismatches=%s"
            % (
                company_pu,
                line.price_subtotal,
                line.price_total,
                line.price_unit_company_currency,
                native_line.price_subtotal,
                native_line.price_total,
                mismatches,
            ),
        )
        self.assertAlmostEqual(line.price_unit_company_currency, company_pu)
        return native

    def test_included_tax_matches_native_company_invoice(self):
        """116 with 16% included at rate 2 is a company unit of 58, base 50."""
        tax = self._included_percent_tax(16)
        foreign = self._create_taxed_move(
            self.foreign_currency, tax, price_unit=116.0
        )
        line = foreign.invoice_line_ids
        self.assertAlmostEqual(foreign.invoice_currency_rate, 2.0)
        self.assertAlmostEqual(line.price_total, 116.0)
        self.assertAlmostEqual(line.price_subtotal, 100.0)
        self._assert_included_matches_native_company_invoice(foreign, 116.0)
        foreign.action_post()
        self._assert_included_matches_native_company_invoice(foreign, 116.0)

    def test_included_tax_rounding_keeps_paid_company_total(self):
        """7.00 with 16% included stays 7.00. base * 16% would book 6.99."""
        tax = self._included_percent_tax(16)
        foreign = self._create_taxed_move(
            self.foreign_currency, tax, price_unit=14.0
        )
        self._assert_included_matches_native_company_invoice(foreign, 14.0)
        line = foreign.invoice_line_ids
        self.assertAlmostEqual(line.price_subtotal_currency, 6.03, places=2)
        self.assertAlmostEqual(line.price_total_currency, 7.00, places=2)

    def test_included_tax_quantity_matches_native_company_invoice(self):
        tax = self._included_percent_tax(16)
        foreign = self._create_taxed_move(
            self.foreign_currency,
            tax,
            price_unit=116.0,
            quantity=3.0,
        )
        line = foreign.invoice_line_ids
        self.assertAlmostEqual(line.price_total, 348.0)
        self.assertAlmostEqual(line.price_subtotal, 300.0)
        self._assert_included_matches_native_company_invoice(
            foreign, 116.0, quantity=3.0
        )

    def test_included_tax_discount_matches_native_company_invoice(self):
        # Vendor bill: customer invoices may forbid per-line discount in this DB.
        tax = self._included_percent_tax(16, type_tax_use="purchase")
        foreign = self._create_taxed_move(
            self.foreign_currency,
            tax,
            price_unit=116.0,
            quantity=2.0,
            discount=10.0,
            move_type="in_invoice",
        )
        line = foreign.invoice_line_ids
        self.assertAlmostEqual(line.price_total, 208.8)
        self.assertAlmostEqual(line.price_subtotal, 180.0)
        self._assert_included_matches_native_company_invoice(
            foreign,
            116.0,
            quantity=2.0,
            discount=10.0,
            move_type="in_invoice",
        )

    def test_included_tax_fractional_unit_matches_native_company_invoice(self):
        """Included unit with many decimals still uses the rounded company unit."""
        self.env.company.tax_calculation_rounding_method = "round_globally"
        tax = self._included_percent_tax(16)
        currency = self.setup_other_currency(
            "EUR",
            rates=[("2026-10-01", BCV_LIKE_RATE)],
        )
        price_unit = 1.43234234 * 1.16
        foreign = self._create_taxed_move(
            currency,
            tax,
            price_unit=price_unit,
            invoice_date="2026-10-23",
        )
        line = foreign.invoice_line_ids
        self.assertGreater(line.price_total, line.price_subtotal)
        self.assertTrue(line.tax_ids.price_include)
        self._assert_included_matches_native_company_invoice(
            foreign,
            price_unit,
            invoice_date="2026-10-23",
        )
        foreign.action_post()
        self._assert_included_matches_native_company_invoice(
            foreign,
            price_unit,
            invoice_date="2026-10-23",
        )

    def test_included_tax_manual_company_total_extracts_base(self):
        """Typing the company total of an included tax stores the company base."""
        tax = self._included_percent_tax(16)
        foreign = self._create_taxed_move(
            self.foreign_currency, tax, price_unit=116.0
        )
        with Form(foreign) as move_form:
            with move_form.invoice_line_ids.edit(0) as line_form:
                line_form.price_total_currency = 46.4
                self.assertTrue(line_form.manually_price_subtotal_currency)
                self.assertAlmostEqual(line_form.price_subtotal_currency, 40.0)
        line = foreign.invoice_line_ids
        self.assertAlmostEqual(line.price_total, 116.0)
        self.assertAlmostEqual(line.price_subtotal, 100.0)
        self.assertAlmostEqual(line.price_total_currency, 46.4)
        self.assertAlmostEqual(line.price_subtotal_currency, 40.0)
        self.assertAlmostEqual(line.currency_rate, 2.5)
        self.assertAlmostEqual(abs(line.balance), 40.0)


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
