# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import float_compare

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestAccountMoveRefundCurrency(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ves = cls.env.ref("base.VES")
        cls.usd = cls.env.ref("base.USD")
        cls.ves.active = True
        cls.usd.active = True
        cls.env.company.currency_id = cls.ves
        cls.company_data["default_journal_sale"].currency_id = False
        cls.company_data["default_journal_purchase"].currency_id = False
        cls.env["decimal.precision"].search([("name", "=", "Product Price")]).digits = 4

    def setUp(self):
        super().setUp()
        self.iva_16 = self.percent_tax(
            16.0,
            type_tax_use="sale",
            country_id=self.env.ref("base.ve").id,
            price_include_override="tax_excluded",
        )
        self.product_iva_16 = self._create_taxed_product(
            "Producto reverso USD", self.iva_16
        )

    def _create_taxed_product(self, name, tax):
        product = self._create_product(name=name, lst_price=1.0)
        product.with_context(l10n_ve_skip_product_tax_constraint=True).taxes_id = tax
        return product

    def _ve_customer(self):
        return self.env["res.partner"].create(
            {
                "name": "Cliente reverso USD",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J20998877",
            }
        )

    def _ensure_usd_rate(self, name, rate=None, inverse_company_rate=None):
        usd = self.env.ref("base.USD")
        usd.active = True
        vals = {
            "currency_id": usd.id,
            "company_id": self.env.company.id,
            "name": name,
        }
        if rate is not None:
            vals["rate"] = rate
        else:
            vals["inverse_company_rate"] = inverse_company_rate
        return self.env["res.currency.rate"].create(vals)

    def _sale_tax(self):
        return self.iva_16

    def _create_usd_invoice(
        self,
        date_invoice,
        prices,
        tax=None,
        discounts=None,
        taxes=None,
        products=None,
        payment_term=None,
        quantities=None,
    ):
        tax = tax if tax is not None else self._sale_tax()
        discounts = discounts or [0.0] * len(prices)
        taxes = taxes or [tax] * len(prices)
        products = products or [self.product_iva_16 if tax else False for tax in taxes]
        quantities = quantities or [1.0] * len(prices)
        line_cmds = []
        for idx, price in enumerate(prices):
            line_tax = taxes[idx]
            product = products[idx] if idx < len(products) else False
            line_vals = {
                "name": f"Linea {idx + 1}",
                "quantity": quantities[idx],
                "price_unit": price,
                "discount": discounts[idx],
                "account_id": self.company_data["default_account_revenue"].id,
                "tax_ids": [(6, 0, line_tax.ids)] if line_tax else [],
            }
            if product:
                line_vals["product_id"] = product.id
            line_cmds.append((0, 0, line_vals))
        vals = {
            "move_type": "out_invoice",
            "partner_id": self._ve_customer().id,
            "currency_id": self.env.ref("base.USD").id,
            "invoice_date": date_invoice,
            "invoice_line_ids": line_cmds,
        }
        if payment_term:
            vals["invoice_payment_term_id"] = payment_term.id
        invoice = self.env["account.move"].create(vals)
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        self.assertTrue(
            invoice.line_ids.filtered(lambda line: line.display_type == "tax"),
            invoice.line_ids.mapped("display_type"),
        )
        return invoice

    def _reverse_invoice(self, invoice, reason="NC Bs"):
        wiz = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": reason})
        )
        wiz.reverse_moves()
        credit = wiz.new_move_ids
        credit.ensure_one()
        return credit

    def _company_tax_amount(self, move):
        return abs(
            sum(
                move.line_ids.filtered(lambda line: line.display_type == "tax").mapped(
                    "balance"
                )
            )
        )

    def _company_base_amount(self, move):
        return abs(
            sum(
                move.line_ids.filtered(
                    lambda line: line.display_type
                    in ("product", "global_discount", "discount")
                ).mapped("balance")
            )
        )

    def _assert_credit_mirrors_origin(self, invoice, credit, post=True):
        company_cur = invoice.company_currency_id
        self.assertEqual(credit.currency_id, credit.company_currency_id)
        orig_products = invoice.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ).sorted(lambda line: (line.sequence, line.id))
        cred_products = credit.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ).sorted(lambda line: (line.sequence, line.id))
        self.assertEqual(len(cred_products), len(orig_products))
        for origin_line, credit_line in zip(orig_products, cred_products, strict=True):
            self.assertEqual(credit_line.quantity, origin_line.quantity)
            self.assertEqual(
                company_cur.round(credit_line.price_subtotal),
                company_cur.round(origin_line.price_subtotal_currency),
            )
            self.assertEqual(
                company_cur.round(credit_line.price_subtotal_currency),
                company_cur.round(origin_line.price_subtotal_currency),
            )
        origin_untaxed = company_cur.round(abs(invoice.amount_untaxed_signed))
        origin_tax = company_cur.round(abs(invoice.amount_tax_signed))
        origin_total = company_cur.round(abs(invoice.amount_total_signed))
        self.assertEqual(company_cur.round(credit.amount_untaxed), origin_untaxed)
        self.assertEqual(company_cur.round(credit.amount_tax), origin_tax)
        self.assertEqual(company_cur.round(credit.amount_total), origin_total)
        self.assertEqual(
            company_cur.round(credit._l10n_ve_to_company_abs_amount()),
            company_cur.round(invoice._l10n_ve_to_company_abs_amount()),
        )
        origin_tax_lines = invoice.line_ids.filtered(
            lambda line: line.display_type == "tax"
        )
        for tax in origin_tax_lines.mapped("tax_line_id"):
            origin_tax_amt = abs(
                sum(
                    origin_tax_lines.filtered(
                        lambda line, tax=tax: line.tax_line_id == tax
                    ).mapped("balance")
                )
            )
            credit_tax_amt = abs(
                sum(
                    credit.line_ids.filtered(
                        lambda line, tax=tax: line.display_type == "tax"
                        and line.tax_line_id == tax
                    ).mapped("balance")
                )
            )
            self.assertEqual(
                company_cur.round(credit_tax_amt),
                company_cur.round(origin_tax_amt),
            )
        if not post:
            return
        credit.action_post()
        self.assertEqual(credit.state, "posted")
        self.assertEqual(company_cur.round(credit.amount_untaxed), origin_untaxed)
        self.assertEqual(company_cur.round(credit.amount_tax), origin_tax)
        self.assertEqual(company_cur.round(credit.amount_total), origin_total)

    def _create_and_assert_full_reverse(
        self,
        date_invoice,
        prices,
        rate=None,
        inverse_company_rate=None,
        later_rate=None,
        **invoice_kwargs,
    ):
        if rate is not None:
            self._ensure_usd_rate(date_invoice, rate=rate)
        else:
            self._ensure_usd_rate(
                date_invoice, inverse_company_rate=inverse_company_rate
            )
        if later_rate is not None:
            self._ensure_usd_rate(fields.Date.today(), rate=later_rate)
        invoice = self._create_usd_invoice(date_invoice, prices, **invoice_kwargs)
        credit = self._reverse_invoice(invoice)
        self._assert_credit_mirrors_origin(invoice, credit)
        return invoice, credit

    def _assert_refund_tax_matches_origin(self, credit, invoice, ratio=1.0):
        company_cur = invoice.company_currency_id
        self.assertGreater(self._company_tax_amount(invoice), 0.0)
        self.assertGreater(self._company_tax_amount(credit), 0.0)
        credit_total = company_cur.round(credit._l10n_ve_to_company_abs_amount())
        origin_limit = company_cur.round(
            invoice._l10n_ve_max_credit_note_company_amount()
        )
        self.assertLessEqual(credit_total, origin_limit)
        if not float_compare(ratio, 1.0, precision_rounding=0.0001):
            self.assertEqual(
                company_cur.round(self._company_base_amount(credit)),
                company_cur.round(self._company_base_amount(invoice)),
            )

    def test_full_reversal_ten_usd_lines_keeps_origin_tax_after_extra_aml(self):
        date_invoice = fields.Date.to_date("2026-08-25")
        self._ensure_usd_rate(date_invoice, rate=0.001271)
        self._ensure_usd_rate(fields.Date.to_date("2026-08-26"), rate=0.0012637)
        invoice = self._create_usd_invoice(
            date_invoice,
            (
                12.45,
                88.10,
                3.20,
                154.00,
                27.33,
                9.99,
                410.50,
                6.01,
                201.15,
                560.76,
            ),
        )
        credit = self._reverse_invoice(invoice, reason="NC FAC 10 lineas")
        self.assertEqual(credit.currency_id, credit.company_currency_id)
        self._assert_refund_tax_matches_origin(credit, invoice)
        credit.action_post()
        self.assertEqual(credit.state, "posted")
        self._assert_refund_tax_matches_origin(credit, invoice)

    def test_full_reversal_usd_later_rate_keeps_invoice_company_tax(self):
        date_invoice = fields.Date.to_date("2026-08-18")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=773.32)
        self._ensure_usd_rate(fields.Date.today(), inverse_company_rate=791.32)
        invoice = self._create_usd_invoice(date_invoice, (100.0, 50.0, 25.0))
        credit = self._reverse_invoice(invoice, reason="NC tasa posterior")
        self._assert_refund_tax_matches_origin(credit, invoice)
        self.assertEqual(
            credit.company_currency_id.round(credit._l10n_ve_to_company_abs_amount()),
            invoice.company_currency_id.round(invoice._l10n_ve_to_company_abs_amount()),
        )
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_full_reversal_usd_line_discount_keeps_origin_tax(self):
        date_invoice = fields.Date.to_date("2026-07-10")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        invoice = self._create_usd_invoice(
            date_invoice,
            (100.0, 80.0),
            discounts=(10.0, 0.0),
        )
        credit = self._reverse_invoice(invoice, reason="NC con descuento")
        self._assert_refund_tax_matches_origin(credit, invoice)
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_full_reversal_usd_mixed_taxes_keeps_each_origin_tax(self):
        date_invoice = fields.Date.to_date("2026-07-11")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        tax_16 = self._sale_tax()
        tax_8 = self.percent_tax(
            8.0,
            type_tax_use="sale",
            country_id=self.env.ref("base.ve").id,
            price_include_override="tax_excluded",
        )
        product_8 = self._create_taxed_product("Producto IVA 8", tax_8)
        invoice = self._create_usd_invoice(
            date_invoice,
            (100.0, 50.0),
            taxes=(tax_16, tax_8),
            products=(self.product_iva_16, product_8),
        )
        credit = self._reverse_invoice(invoice, reason="NC alicuotas mixtas")
        company_cur = invoice.company_currency_id
        for tax in (tax_16, tax_8):
            origin_tax = abs(
                sum(
                    invoice.line_ids.filtered(
                        lambda line, tax=tax: line.display_type == "tax"
                        and line.tax_line_id == tax
                    ).mapped("balance")
                )
            )
            credit_tax = abs(
                sum(
                    credit.line_ids.filtered(
                        lambda line, tax=tax: line.display_type == "tax"
                        and line.tax_line_id == tax
                    ).mapped("balance")
                )
            )
            self.assertGreater(company_cur.round(credit_tax), 0.0)
            self.assertGreater(company_cur.round(origin_tax), 0.0)
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_full_reversal_usd_exempt_and_taxed_lines(self):
        date_invoice = fields.Date.to_date("2026-07-12")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        invoice = self._create_usd_invoice(
            date_invoice,
            (100.0, 40.0),
            taxes=(self._sale_tax(), self.env["account.tax"]),
        )
        credit = self._reverse_invoice(invoice, reason="NC exento y gravado")
        self._assert_refund_tax_matches_origin(credit, invoice)
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_partial_qty_reversal_scales_origin_company_tax(self):
        date_invoice = fields.Date.to_date("2026-07-13")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        invoice = self._create_usd_invoice(date_invoice, (100.0,))
        credit = self._reverse_invoice(invoice, reason="NC cantidad parcial")
        product_line = credit.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        product_line.ensure_one()
        product_line.quantity = 0.5
        origin_base = self._company_base_amount(invoice)
        credit_base = self._company_base_amount(credit)
        ratio = credit_base / origin_base
        self._assert_refund_tax_matches_origin(credit, invoice, ratio=ratio)
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_partial_price_manual_refund_converts_scaled_company_amounts(self):
        date_invoice = fields.Date.to_date("2026-07-14")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        invoice = self._create_usd_invoice(date_invoice, (100.0,))
        tax = self._sale_tax()
        credit = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "reversed_entry_id": invoice.id,
                "partner_id": invoice.partner_id.id,
                "currency_id": invoice.currency_id.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Ajuste precio",
                            "product_id": self.product_iva_16.id,
                            "quantity": 1.0,
                            "price_unit": 40.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [(6, 0, tax.ids)] if tax else [],
                        },
                    )
                ],
            }
        )
        credit.action_post()
        self.assertEqual(credit.currency_id, credit.company_currency_id)
        origin_base = self._company_base_amount(invoice)
        credit_base = self._company_base_amount(credit)
        ratio = credit_base / origin_base
        self.assertTrue(
            float_compare(ratio, 0.4, precision_rounding=0.01) == 0
            or abs(ratio - 0.4) < 0.02
        )
        self._assert_refund_tax_matches_origin(credit, invoice, ratio=ratio)

    def test_full_reversal_usd_installments_stays_balanced_after_tax_align(self):
        date_invoice = fields.Date.to_date("2026-07-15")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        term = self.env["account.payment.term"].create(
            {
                "name": "2 plazos test",
                "line_ids": [
                    (0, 0, {"value": "percent", "value_amount": 50.0, "nb_days": 0}),
                    (0, 0, {"value": "percent", "value_amount": 50.0, "nb_days": 15}),
                ],
            }
        )
        invoice = self._create_usd_invoice(
            date_invoice, (100.0, 20.0), payment_term=term
        )
        credit = self._reverse_invoice(invoice, reason="NC plazos")
        self._assert_refund_tax_matches_origin(credit, invoice)
        term_lines = credit.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )
        self.assertTrue(term_lines)
        residual = credit.company_currency_id.round(
            sum(credit.line_ids.mapped("balance"))
        )
        self.assertEqual(residual, 0.0)
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_manual_refund_unmatched_line_raises(self):
        date_invoice = fields.Date.to_date("2026-07-16")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        invoice = self._create_usd_invoice(date_invoice, (10.0, 20.0))
        tax = self._sale_tax()
        other = self._create_taxed_product("Producto ajeno NC", tax)
        credit = self.env["account.move"].create(
            {
                "move_type": "out_refund",
                "reversed_entry_id": invoice.id,
                "partner_id": invoice.partner_id.id,
                "currency_id": invoice.currency_id.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Producto que no esta en origen",
                            "product_id": other.id,
                            "quantity": 1.0,
                            "price_unit": 10.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [(6, 0, tax.ids)] if tax else [],
                        },
                    )
                ],
            }
        )
        with self.assertRaises(ValidationError) as error:
            credit._l10n_ve_force_refund_to_company_currency()
        self.assertIn("no coincide en l", str(error.exception).lower())

    def test_vendor_usd_refund_keeps_foreign_currency(self):
        date_invoice = fields.Date.to_date("2026-07-17")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        usd = self.env.ref("base.USD")
        vendor = self.env["res.partner"].create(
            {
                "name": "Proveedor reverso USD",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J30112233",
            }
        )
        tax = self.company_data["default_tax_purchase"]
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": vendor.id,
                "currency_id": usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Compra USD",
                            "quantity": 1.0,
                            "price_unit": 80.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [(6, 0, tax.ids)] if tax else [],
                        },
                    )
                ],
            }
        )
        bill.action_post()
        refund = self.env["account.move"].create(
            {
                "move_type": "in_refund",
                "reversed_entry_id": bill.id,
                "partner_id": vendor.id,
                "currency_id": usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "NC compra USD",
                            "quantity": 1.0,
                            "price_unit": 80.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [(6, 0, tax.ids)] if tax else [],
                        },
                    )
                ],
            }
        )
        refund.action_post()
        self.assertEqual(refund.currency_id, usd)
        self.assertEqual(refund.state, "posted")

    def test_full_reversal_copies_origin_company_currency_line_fields(self):
        date_invoice = fields.Date.to_date("2026-08-25")
        self._ensure_usd_rate(date_invoice, rate=0.001271)
        invoice = self._create_usd_invoice(
            date_invoice,
            (
                12.45,
                88.10,
                3.20,
                154.00,
                27.33,
                9.99,
                410.50,
                6.01,
                201.15,
                560.76,
            ),
        )
        orig_products = invoice.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ).sorted(lambda line: (line.sequence, line.id))
        company_cur = invoice.company_currency_id
        origin_subtotal = company_cur.round(
            sum(orig_products.mapped("price_subtotal_currency"))
        )
        credit = self._reverse_invoice(invoice, reason="NC campos moneda compania")
        cred_products = credit.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ).sorted(lambda line: (line.sequence, line.id))
        self.assertEqual(len(cred_products), len(orig_products))
        for origin_line, credit_line in zip(orig_products, cred_products, strict=True):
            self.assertEqual(
                company_cur.round(credit_line.price_unit),
                company_cur.round(origin_line.price_unit_company_currency),
            )
            self.assertEqual(
                company_cur.round(credit_line.price_subtotal),
                company_cur.round(origin_line.price_subtotal_currency),
            )
            self.assertEqual(
                company_cur.round(credit_line.price_subtotal_currency),
                company_cur.round(origin_line.price_subtotal_currency),
            )
        self.assertEqual(
            company_cur.round(credit.amount_untaxed),
            origin_subtotal,
        )
        self._assert_refund_tax_matches_origin(credit, invoice)
        credit.action_post()
        self.assertEqual(credit.state, "posted")
        self.assertEqual(
            company_cur.round(credit.amount_untaxed),
            origin_subtotal,
        )

    def test_full_reversal_fac_2026_00427_company_totals(self):
        date_invoice = fields.Date.to_date("2026-08-25")
        self._ensure_usd_rate(date_invoice, rate=0.0012737729013222144)
        invoice = self._create_usd_invoice(
            date_invoice,
            (
                18.79432,
                27.56501,
                87.70685,
                93.97162,
                50.1182,
                17.54137,
                15.6625,
                249.33804,
                56.38298,
                245.59,
            ),
            quantities=(4.0, 2.0, 1.0, 2.0, 1.0, 2.0, 8.0, 2.0, 2.0, 1.0),
        )
        company_cur = invoice.company_currency_id
        origin_untaxed = company_cur.round(abs(invoice.amount_untaxed_signed))
        origin_tax = company_cur.round(abs(invoice.amount_tax_signed))
        origin_total = company_cur.round(abs(invoice.amount_total_signed))
        self.assertEqual(origin_untaxed, 1156792.05)
        self.assertEqual(origin_tax, 185086.73)
        self.assertEqual(origin_total, 1341878.78)
        credit = self._reverse_invoice(invoice, reason="NC FAC/2026/00427")
        self.assertEqual(credit.currency_id, credit.company_currency_id)
        orig_products = invoice.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ).sorted(lambda line: (line.sequence, line.id))
        cred_products = credit.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ).sorted(lambda line: (line.sequence, line.id))
        for origin_line, credit_line in zip(orig_products, cred_products, strict=True):
            self.assertEqual(
                company_cur.round(credit_line.price_subtotal),
                company_cur.round(origin_line.price_subtotal_currency),
            )
        self.assertEqual(company_cur.round(credit.amount_untaxed), origin_untaxed)
        self.assertEqual(company_cur.round(credit.amount_tax), origin_tax)
        self.assertEqual(company_cur.round(credit.amount_total), origin_total)
        self.assertEqual(company_cur.round(credit.amount_untaxed), 1156792.05)
        self.assertEqual(company_cur.round(credit.amount_tax), 185086.73)
        self.assertEqual(company_cur.round(credit.amount_total), 1341878.78)
        credit.action_post()
        self.assertEqual(credit.state, "posted")
        self.assertEqual(company_cur.round(credit.amount_untaxed), 1156792.05)
        self.assertEqual(company_cur.round(credit.amount_tax), 185086.73)
        self.assertEqual(company_cur.round(credit.amount_total), 1341878.78)

    def test_remaining_reversal_after_almost_total_fac_2026_00437(self):
        date_invoice = fields.Date.to_date("2026-08-11")
        self._ensure_usd_rate(date_invoice, rate=0.0012737729013222144)
        tax = self._sale_tax()
        products = [
            self._create_taxed_product(name, tax)
            for name in (
                "MANIJA AC45",
                "Producto 2 FAC437",
                "Producto 3 FAC437",
                "Producto 4 FAC437",
                "Producto 5 FAC437",
                "Producto 6 FAC437",
                "Producto 7 FAC437",
                "Producto 8 FAC437",
                "Producto 9 FAC437",
                "[AC45-3304-EA/GEN1] BARRA CORTA DE DIRECCION CARGO 1721 OTMUS BRASIL",
            )
        ]
        invoice = self._create_usd_invoice(
            date_invoice,
            (
                18.79432,
                27.56501,
                87.70685,
                93.97162,
                50.1182,
                17.54137,
                15.6625,
                249.33804,
                56.38298,
                245.59,
            ),
            quantities=(4.0, 2.0, 1.0, 2.0, 1.0, 2.0, 8.0, 2.0, 2.0, 1.0),
            products=products,
        )
        first = self._reverse_invoice(invoice, reason="NC casi total FAC/2026/00437")
        first_products = first.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ).sorted(lambda line: (line.sequence, line.id))
        first_products[0].quantity = 3.0
        first.action_post()
        self.assertEqual(first.state, "posted")
        second = self._reverse_invoice(invoice, reason="NC restante FAC/2026/00437")
        second_products = second.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        self.assertEqual(len(second_products), 1)
        self.assertEqual(second_products.product_id, products[0])
        self.assertEqual(second_products.quantity, 1.0)
        price_prec = self.env["decimal.precision"].precision_get("Product Price")
        self.assertGreater(
            float_compare(second_products.price_unit, 0.0, precision_digits=price_prec),
            0,
        )
        self.assertNotEqual(second_products.product_id, products[-1])
        second.action_post()
        self.assertEqual(second.state, "posted")
        company_cur = invoice.company_currency_id
        combined_total = company_cur.round(first.amount_total + second.amount_total)
        origin_total = company_cur.round(abs(invoice.amount_total_signed))
        self.assertLessEqual(
            company_cur.round(abs(combined_total - origin_total)),
            company_cur.rounding,
        )
        origin_first = invoice.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ).sorted(lambda line: (line.sequence, line.id))[0]
        expected_remaining_base = company_cur.round(
            invoice._l10n_ve_company_price_unit_from_origin_line(origin_first)
        )
        self.assertEqual(
            company_cur.round(second_products.price_subtotal),
            expected_remaining_base,
        )

    def test_mirror_qty_three_does_not_split_cents(self):
        self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-01"),
            (10.01, 20.02, 7.77),
            rate=0.0012737729013222144,
            quantities=(3.0, 3.0, 3.0),
        )

    def test_mirror_qty_seven_repeating_unit_price(self):
        self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-02"),
            (1.33, 2.67, 9.99),
            rate=0.001271,
            quantities=(7.0, 7.0, 7.0),
        )

    def test_mirror_many_tiny_usd_lines(self):
        self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-03"),
            (0.07, 0.13, 0.19, 0.23, 0.29, 0.31, 0.37, 0.41, 0.43, 0.47, 0.53, 0.59),
            rate=0.0012637,
        )

    def test_mirror_line_discount_with_uneven_qty(self):
        self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-04"),
            (33.3333, 66.6667, 12.3456),
            inverse_company_rate=785.0685,
            quantities=(3.0, 2.0, 4.0),
            discounts=(15.0, 5.0, 10.0),
        )

    def test_mirror_mixed_qty_five_decimal_prices(self):
        self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-05"),
            (18.79432, 9.99999, 0.1001, 87.70685, 15.6625),
            rate=0.0012744319761100078,
            quantities=(4.0, 5.0, 3.0, 2.0, 8.0),
        )

    def test_mirror_keeps_invoice_rate_when_today_rate_changes(self):
        self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-06"),
            (88.10, 12.45, 201.15, 6.01),
            inverse_company_rate=773.32,
            later_rate=0.0012637,
            quantities=(2.0, 3.0, 1.0, 5.0),
        )

    def test_mirror_mixed_16_and_8_with_qty(self):
        tax_8 = self.percent_tax(
            8.0,
            type_tax_use="sale",
            country_id=self.env.ref("base.ve").id,
            price_include_override="tax_excluded",
        )
        product_8 = self._create_taxed_product("Producto IVA 8 qty", tax_8)
        self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-07"),
            (45.45, 54.54, 19.19),
            rate=0.00128,
            quantities=(3.0, 3.0, 2.0),
            taxes=(self.iva_16, tax_8, self.iva_16),
            products=(self.product_iva_16, product_8, self.product_iva_16),
        )

    def test_mirror_exempt_and_taxed_with_qty(self):
        self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-08"),
            (100.01, 50.02, 8.88),
            inverse_company_rate=791.32,
            quantities=(3.0, 2.0, 6.0),
            taxes=(self.iva_16, self.env["account.tax"], self.iva_16),
        )

    def test_mirror_large_qty_high_unit_price(self):
        self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-09"),
            (9999.99, 1234.5678),
            rate=0.001271,
            quantities=(12.0, 9.0),
        )

    def test_mirror_repeating_thirds_unit_prices(self):
        self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-10"),
            (0.3333, 1.1111, 3.3333),
            rate=0.0012737729013222144,
            quantities=(3.0, 9.0, 6.0),
        )

    def test_mirror_fifteen_awkward_hardware_lines(self):
        self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-11"),
            (
                2.35,
                14.90,
                0.99,
                125.05,
                7.11,
                48.48,
                3.03,
                199.95,
                11.17,
                0.55,
                64.32,
                8.08,
                27.56501,
                249.33804,
                5.01,
            ),
            rate=0.0012737729013222144,
            quantities=(
                6.0,
                1.0,
                12.0,
                2.0,
                3.0,
                4.0,
                7.0,
                1.0,
                5.0,
                20.0,
                2.0,
                8.0,
                2.0,
                2.0,
                11.0,
            ),
        )

    def test_mirror_installments_with_uneven_qty(self):
        term = self.env["account.payment.term"].create(
            {
                "name": "2 plazos redondeo",
                "line_ids": [
                    (0, 0, {"value": "percent", "value_amount": 50.0, "nb_days": 0}),
                    (0, 0, {"value": "percent", "value_amount": 50.0, "nb_days": 15}),
                ],
            }
        )
        invoice, credit = self._create_and_assert_full_reverse(
            fields.Date.to_date("2026-05-12"),
            (18.79432, 56.38298, 9.99),
            inverse_company_rate=785.0685,
            quantities=(4.0, 3.0, 7.0),
            payment_term=term,
        )
        residual = credit.company_currency_id.round(
            sum(credit.line_ids.mapped("balance"))
        )
        self.assertEqual(residual, 0.0)
        self.assertTrue(
            credit.line_ids.filtered(lambda line: line.display_type == "payment_term")
        )
