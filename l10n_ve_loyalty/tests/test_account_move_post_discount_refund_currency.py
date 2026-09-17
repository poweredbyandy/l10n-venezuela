# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.l10n_ve_loyalty.tests.common import L10nVeLoyaltyCommon


@tagged("post_install", "-at_install")
class TestAccountMovePostDiscountRefundCurrency(L10nVeLoyaltyCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ves = cls.env.ref("base.VES")
        cls.usd = cls.env.ref("base.USD")
        cls.ves.active = True
        cls.usd.active = True
        cls.env.company.currency_id = cls.ves
        cls.company_data["default_journal_sale"].currency_id = False
        cls._l10n_ve_configure_journal_free(cls.company_data["default_journal_sale"])
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner VE post discount USD",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J20991122",
            }
        )
        cls.reason_early = cls.env.ref(
            "l10n_ve_loyalty.l10n_ve_discount_reason_early_payment",
            raise_if_not_found=False,
        )
        if not cls.reason_early:
            cls.reason_early = cls.env["l10n.ve.discount.reason"].create(
                {"name": "Pronto pago"}
            )

    def setUp(self):
        super().setUp()
        self.iva_16 = self.percent_tax(
            16.0,
            type_tax_use="sale",
            country_id=self.env.ref("base.ve").id,
            price_include_override="tax_excluded",
        )
        self.product_iva_16 = self._create_taxed_product(
            "Producto descuento USD", self.iva_16
        )

    def _create_taxed_product(self, name, tax):
        product = self._create_product(name=name, lst_price=1.0)
        product.with_context(l10n_ve_skip_product_tax_constraint=True).taxes_id = tax
        return product

    def _ensure_usd_rate(self, name, inverse_company_rate=None, rate=None):
        vals = {
            "currency_id": self.usd.id,
            "company_id": self.env.company.id,
            "name": name,
        }
        if rate is not None:
            vals["rate"] = rate
        else:
            vals["inverse_company_rate"] = inverse_company_rate
        return self.env["res.currency.rate"].create(vals)

    def _create_usd_invoice(
        self, date_invoice, prices, discounts=None, taxes=None, products=None
    ):
        discounts = discounts or [0.0] * len(prices)
        taxes = taxes or [self.iva_16] * len(prices)
        products = products or [self.product_iva_16 if tax else False for tax in taxes]
        lines = []
        for idx, price in enumerate(prices):
            line_tax = taxes[idx]
            product = products[idx] if idx < len(products) else False
            vals = {
                "name": "Linea %s" % (idx + 1),
                "quantity": 1.0,
                "price_unit": price,
                "discount": discounts[idx],
                "account_id": self.company_data["default_account_revenue"].id,
                "tax_ids": [Command.set(line_tax.ids)] if line_tax else [],
            }
            if product:
                vals["product_id"] = product.id
            lines.append(Command.create(vals))
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "currency_id": self.usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": lines,
            }
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        self.assertTrue(
            invoice.line_ids.filtered(lambda line: line.display_type == "tax"),
            invoice.line_ids.mapped("display_type"),
        )
        return invoice

    def _apply_post_discount(self, invoice, mode="amount", amount=0.0, percentage=0.1):
        wizard = self.env["l10n.ve.account.move.discount.wizard"].create(
            {
                "move_id": invoice.id,
                "reason_id": self.reason_early.id,
                "discount_mode": mode,
                "discount_percentage": percentage,
                "amount": amount,
                "amount_base": "untaxed",
                "discount_currency_id": invoice.currency_id.id,
            }
        )
        action = wizard.action_apply_discount()
        credit = self.env["account.move"].browse(action["res_id"])
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

    def _assert_post_discount_tax_scaled(self, credit, invoice):
        company_cur = invoice.company_currency_id
        origin_base = self._company_base_amount(invoice)
        credit_base = self._company_base_amount(credit)
        self.assertGreater(origin_base, 0.0)
        self.assertGreater(credit_base, 0.0)
        ratio = credit_base / origin_base
        self.assertGreater(self._company_tax_amount(credit), 0.0)
        self.assertGreater(ratio, 0.0)
        self.assertLessEqual(
            company_cur.round(credit._l10n_ve_to_company_abs_amount()),
            company_cur.round(invoice._l10n_ve_max_credit_note_company_amount()),
        )

    def test_post_discount_ten_usd_lines_keeps_scaled_origin_tax(self):
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
        credit = self._apply_post_discount(invoice, mode="percentage", percentage=0.1)
        self.assertTrue(credit._l10n_ve_is_post_discount_credit_note())
        self.assertEqual(credit.currency_id, invoice.currency_id)
        self._assert_post_discount_tax_scaled(credit, invoice)
        credit.action_post()
        self.assertEqual(credit.state, "posted")
        self._assert_post_discount_tax_scaled(credit, invoice)

    def test_post_discount_usd_later_rate_uses_invoice_company_amounts(self):
        date_invoice = fields.Date.to_date("2026-08-18")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=773.32)
        self._ensure_usd_rate(fields.Date.today(), inverse_company_rate=791.32)
        invoice = self._create_usd_invoice(date_invoice, (100.0, 50.0, 25.0))
        credit = self._apply_post_discount(invoice, mode="amount", amount=17.50)
        expected_bs = invoice._l10n_ve_post_discount_amount_in_currency(
            17.50, invoice.company_currency_id
        )
        self.assertEqual(credit.currency_id, invoice.currency_id)
        self.assertAlmostEqual(credit.amount_untaxed, 17.50, places=2)
        company_cur = invoice.company_currency_id
        self.assertAlmostEqual(
            company_cur.round(self._company_base_amount(credit)),
            company_cur.round(expected_bs),
            places=2,
        )
        later_bs = company_cur.round(17.50 * 791.32)
        self.assertNotAlmostEqual(
            company_cur.round(self._company_base_amount(credit)),
            later_bs,
            places=0,
        )
        self._assert_post_discount_tax_scaled(credit, invoice)
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_post_discount_usd_line_discount_keeps_scaled_tax(self):
        date_invoice = fields.Date.to_date("2026-07-10")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        invoice = self._create_usd_invoice(
            date_invoice,
            (100.0, 80.0),
            discounts=(10.0, 0.0),
        )
        credit = self._apply_post_discount(invoice, mode="percentage", percentage=0.2)
        self._assert_post_discount_tax_scaled(credit, invoice)
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_post_discount_usd_mixed_taxes_scales_each_aliquot(self):
        date_invoice = fields.Date.to_date("2026-07-11")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
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
            taxes=(self.iva_16, tax_8),
            products=(self.product_iva_16, product_8),
        )
        credit = self._apply_post_discount(invoice, mode="amount", amount=15.0)
        company_cur = invoice.company_currency_id
        origin_base = self._company_base_amount(invoice)
        credit_base = self._company_base_amount(credit)
        ratio = credit_base / origin_base
        for tax in (self.iva_16, tax_8):
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
            self.assertEqual(
                company_cur.round(credit_tax),
                company_cur.round(origin_tax * ratio),
            )
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_post_discount_after_global_discount_usd_stays_within_origin(self):
        date_invoice = fields.Date.to_date("2026-07-12")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "currency_id": self.usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_iva_16.id,
                            "name": "Linea gravada",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set(self.iva_16.ids)],
                        }
                    )
                ],
            }
        )
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": invoice.id,
                "reason_id": self.reason_early.id,
                "amount": 10.0,
            }
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        credit = self._apply_post_discount(invoice, mode="amount", amount=9.0)
        self._assert_post_discount_tax_scaled(credit, invoice)
        credit.action_post()
        self.assertEqual(credit.state, "posted")
        company_cur = invoice.company_currency_id
        self.assertLessEqual(
            company_cur.round(credit._l10n_ve_to_company_abs_amount()),
            company_cur.round(invoice._l10n_ve_max_credit_note_company_amount()),
        )

    def test_full_reversal_usd_with_line_and_global_discount_keeps_origin_tax(self):
        date_invoice = fields.Date.to_date("2026-07-13")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "currency_id": self.usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_iva_16.id,
                            "name": "Linea con descuento",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "discount": 10.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set(self.iva_16.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": self.product_iva_16.id,
                            "name": "Linea sin descuento",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set(self.iva_16.ids)],
                        }
                    ),
                ],
            }
        )
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": invoice.id,
                "reason_id": self.reason_early.id,
                "amount": 14.0,
            }
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        wiz = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": "NC total con descuentos"})
        )
        wiz.reverse_moves()
        credit = wiz.new_move_ids
        credit.ensure_one()
        self._assert_full_reverse_mirrors_origin(invoice, credit)

    def test_full_reversal_usd_with_percentage_global_discount_keeps_origin_tax(self):
        date_invoice = fields.Date.to_date("2026-07-14")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=100.0)
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "currency_id": self.usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_iva_16.id,
                            "name": "Linea con descuento",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "discount": 10.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set(self.iva_16.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": self.product_iva_16.id,
                            "name": "Linea sin descuento",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set(self.iva_16.ids)],
                        }
                    ),
                ],
            }
        )
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": invoice.id,
                "reason_id": self.reason_early.id,
                "discount_type": "percentage",
                "discount_percentage": 0.1,
                "amount": 14.0,
            }
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        wiz = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": "NC total descuento porcentual"})
        )
        wiz.reverse_moves()
        credit = wiz.new_move_ids
        credit.ensure_one()
        self._assert_full_reverse_mirrors_origin(invoice, credit)

    def test_full_reversal_usd_percentage_without_allocation_keeps_origin_amounts(
        self,
    ):
        date_invoice = fields.Date.to_date("2026-09-16")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=846.451)
        self.env.company.account_discount_expense_allocation_id = False
        if "account_discount_income_allocation_id" in self.env.company._fields:
            self.env.company.account_discount_income_allocation_id = False
        prices = [
            (3.0, 168.18),
            (3.0, 6.36),
            (2.0, 33.36),
            (16.0, 19.59),
            (16.0, 16.19),
            (4.0, 17.21),
            (4.0, 24.72),
            (1.0, 68.23),
            (2.0, 89.68),
            (12.0, 17.36),
        ]
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "currency_id": self.usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_iva_16.id,
                            "name": "Linea %s" % idx,
                            "quantity": qty,
                            "price_unit": price,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set(self.iva_16.ids)],
                        }
                    )
                    for idx, (qty, price) in enumerate(prices, start=1)
                ],
            }
        )
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": invoice.id,
                "reason_id": self.reason_early.id,
                "discount_type": "percentage",
                "discount_percentage": 0.1,
                "amount": 178.65,
            }
        )
        invoice.action_post()
        self.assertFalse(invoice._l10n_ve_uses_global_discount_journal_lines())
        invoice.l10n_ve_invoice_original_printed = True
        wiz = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": "NC total sin cuenta de prorrateo"})
        )
        wiz.reverse_moves()
        credit = wiz.new_move_ids
        credit.ensure_one()
        self._assert_full_reverse_mirrors_origin(invoice, credit)

    def test_full_reversal_ves_with_line_and_global_discount_keeps_origin_tax(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "currency_id": self.ves.id,
                "invoice_date": fields.Date.to_date("2026-07-15"),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_iva_16.id,
                            "name": "Linea con descuento",
                            "quantity": 1.0,
                            "price_unit": 10000.0,
                            "discount": 10.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set(self.iva_16.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": self.product_iva_16.id,
                            "name": "Linea sin descuento",
                            "quantity": 1.0,
                            "price_unit": 5000.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set(self.iva_16.ids)],
                        }
                    ),
                ],
            }
        )
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": invoice.id,
                "reason_id": self.reason_early.id,
                "amount": 1400.0,
            }
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        wiz = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": "NC total Bs con descuentos"})
        )
        wiz.reverse_moves()
        credit = wiz.new_move_ids
        credit.ensure_one()
        self._assert_full_reverse_mirrors_origin(invoice, credit)

    def _assert_full_reverse_mirrors_origin(self, invoice, credit):
        self.assertEqual(credit.currency_id, invoice.currency_id)
        self.assertTrue(credit.l10n_ve_global_discount_ids)
        company_cur = invoice.company_currency_id
        self.assertGreater(self._company_tax_amount(credit), 0.0)
        self.assertEqual(
            company_cur.round(self._company_base_amount(credit)),
            company_cur.round(self._company_base_amount(invoice)),
        )
        self.assertEqual(
            company_cur.round(self._company_tax_amount(credit)),
            company_cur.round(self._company_tax_amount(invoice)),
        )
        self.assertEqual(
            company_cur.round(credit._l10n_ve_to_company_abs_amount()),
            company_cur.round(invoice._l10n_ve_to_company_abs_amount()),
        )
        origin_products = invoice.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ).sorted(lambda line: (line.sequence, line.id))
        credit_products = credit.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ).sorted(lambda line: (line.sequence, line.id))
        self.assertEqual(len(origin_products), len(credit_products))
        for origin_line, credit_line in zip(
            origin_products, credit_products, strict=True
        ):
            self.assertEqual(
                company_cur.round(abs(credit_line.balance)),
                company_cur.round(abs(origin_line.balance)),
            )
        self.assertLessEqual(
            company_cur.round(credit._l10n_ve_to_company_abs_amount()),
            company_cur.round(invoice._l10n_ve_max_credit_note_company_amount()),
        )
        self._assert_tax_totals_match_origin_company(invoice, credit)
        credit.action_post()
        self.assertEqual(credit.state, "posted")
        self.assertGreater(self._company_tax_amount(credit), 0.0)
        self.assertEqual(
            company_cur.round(self._company_base_amount(credit)),
            company_cur.round(self._company_base_amount(invoice)),
        )
        self._assert_tax_totals_match_origin_company(invoice, credit)

    def _assert_tax_totals_match_origin_company(self, invoice, credit):
        company_cur = invoice.company_currency_id
        currency = invoice.currency_id
        invoice_totals = invoice.tax_totals or {}
        credit_totals = credit.tax_totals or {}
        for key in ("base_amount", "tax_amount", "total_amount"):
            self.assertEqual(
                company_cur.round(credit_totals.get(key) or 0.0),
                company_cur.round(invoice_totals.get(key) or 0.0),
            )
        for key in (
            "base_amount_currency",
            "tax_amount_currency",
            "total_amount_currency",
        ):
            self.assertEqual(
                currency.round(credit_totals.get(key) or 0.0),
                currency.round(invoice_totals.get(key) or 0.0),
            )



    def _create_usd_invoice_draft(self, date_invoice, prices, discounts=None):
        discounts = discounts or [0.0] * len(prices)
        lines = []
        for idx, price in enumerate(prices):
            lines.append(
                Command.create(
                    {
                        "product_id": self.product_iva_16.id,
                        "name": "Linea %s" % (idx + 1),
                        "quantity": 1.0,
                        "price_unit": price,
                        "discount": discounts[idx],
                        "account_id": self.company_data["default_account_revenue"].id,
                        "tax_ids": [Command.set(self.iva_16.ids)],
                    }
                )
            )
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "currency_id": self.usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": lines,
            }
        )

    def _reverse_invoice(self, invoice, reason="NC test", invoice_date=None):
        wiz = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"reason": reason})
        )
        wiz.reverse_moves()
        credit = wiz.new_move_ids
        credit.ensure_one()
        if invoice_date:
            credit.write(
                {
                    "invoice_date": invoice_date,
                    "invoice_date_due": invoice_date,
                }
            )
        return credit

    def _post_invoice_with_percentage_discount(self, invoice, percentage, amount):
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": invoice.id,
                "reason_id": self.reason_early.id,
                "discount_type": "percentage",
                "discount_percentage": percentage,
                "amount": amount,
            }
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        return invoice

    def test_full_reversal_usd_same_day_keeps_origin_rate_and_amounts(self):
        date_invoice = fields.Date.to_date("2026-09-01")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=846.451)
        invoice = self._create_usd_invoice_draft(date_invoice, (100.0, 50.0))
        self._post_invoice_with_percentage_discount(invoice, 0.1, 15.0)
        credit = self._reverse_invoice(invoice, invoice_date=date_invoice)
        self.assertEqual(credit.invoice_currency_rate, invoice.invoice_currency_rate)
        self._assert_full_reverse_mirrors_origin(invoice, credit)

    def test_full_reversal_usd_next_day_higher_rate_keeps_origin_bs(self):
        date_invoice = fields.Date.to_date("2026-09-02")
        date_credit = fields.Date.to_date("2026-09-03")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=846.451)
        self._ensure_usd_rate(date_credit, inverse_company_rate=900.0)
        invoice = self._create_usd_invoice_draft(date_invoice, (120.0, 80.0))
        self._post_invoice_with_percentage_discount(invoice, 0.1, 20.0)
        credit = self._reverse_invoice(invoice, invoice_date=date_credit)
        self.assertEqual(credit.currency_id, invoice.currency_id)
        self.assertEqual(credit.invoice_currency_rate, invoice.invoice_currency_rate)
        self.assertNotEqual(credit.invoice_date, invoice.invoice_date)
        self._assert_full_reverse_mirrors_origin(invoice, credit)

    def test_full_reversal_usd_earlier_day_lower_rate_keeps_origin_bs(self):
        date_invoice = fields.Date.to_date("2026-09-05")
        date_credit = fields.Date.to_date("2026-09-04")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=846.451)
        self._ensure_usd_rate(date_credit, inverse_company_rate=700.0)
        invoice = self._create_usd_invoice_draft(date_invoice, (90.0, 60.0))
        self._post_invoice_with_percentage_discount(invoice, 0.1, 15.0)
        credit = self._reverse_invoice(invoice, invoice_date=date_credit)
        self.assertEqual(credit.invoice_currency_rate, invoice.invoice_currency_rate)
        self._assert_full_reverse_mirrors_origin(invoice, credit)

    def test_full_reversal_usd_ten_lines_later_rate_without_allocation(self):
        date_invoice = fields.Date.to_date("2026-09-10")
        date_credit = fields.Date.to_date("2026-09-12")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=846.451)
        self._ensure_usd_rate(date_credit, inverse_company_rate=910.0)
        self.env.company.account_discount_expense_allocation_id = False
        if "account_discount_income_allocation_id" in self.env.company._fields:
            self.env.company.account_discount_income_allocation_id = False
        prices = [
            (3.0, 168.18),
            (3.0, 6.36),
            (2.0, 33.36),
            (16.0, 19.59),
            (16.0, 16.19),
            (4.0, 17.21),
            (4.0, 24.72),
            (1.0, 68.23),
            (2.0, 89.68),
            (12.0, 17.36),
        ]
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "currency_id": self.usd.id,
                "invoice_date": date_invoice,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_iva_16.id,
                            "name": "Linea %s" % idx,
                            "quantity": qty,
                            "price_unit": price,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set(self.iva_16.ids)],
                        }
                    )
                    for idx, (qty, price) in enumerate(prices, start=1)
                ],
            }
        )
        self._post_invoice_with_percentage_discount(invoice, 0.1, 178.65)
        credit = self._reverse_invoice(invoice, invoice_date=date_credit)
        self.assertEqual(credit.invoice_currency_rate, invoice.invoice_currency_rate)
        self._assert_full_reverse_mirrors_origin(invoice, credit)

    def test_partial_reversal_usd_later_rate_keeps_origin_ratio_bs(self):
        date_invoice = fields.Date.to_date("2026-09-15")
        date_credit = fields.Date.to_date("2026-09-20")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=800.0)
        self._ensure_usd_rate(date_credit, inverse_company_rate=950.0)
        invoice = self._create_usd_invoice(date_invoice, (100.0, 100.0))
        credit = self._reverse_invoice(invoice, invoice_date=date_credit)
        line = credit.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )[:1]
        line.quantity = 0.5
        company_cur = invoice.company_currency_id
        self.assertEqual(credit.currency_id, invoice.currency_id)
        self.assertEqual(credit.invoice_currency_rate, invoice.invoice_currency_rate)
        self.assertLess(
            company_cur.round(credit._l10n_ve_to_company_abs_amount()),
            company_cur.round(invoice._l10n_ve_to_company_abs_amount()),
        )
        self.assertLessEqual(
            company_cur.round(credit._l10n_ve_to_company_abs_amount()),
            company_cur.round(invoice._l10n_ve_max_credit_note_company_amount()),
        )
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_two_partial_refunds_different_dates_sum_origin_bs(self):
        date_invoice = fields.Date.to_date("2026-09-21")
        date_first = fields.Date.to_date("2026-09-22")
        date_second = fields.Date.to_date("2026-09-25")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=810.0)
        self._ensure_usd_rate(date_first, inverse_company_rate=820.0)
        self._ensure_usd_rate(date_second, inverse_company_rate=880.0)
        invoice = self._create_usd_invoice(date_invoice, (200.0,))
        first = self._reverse_invoice(
            invoice, reason="NC parcial 1", invoice_date=date_first
        )
        product = first.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        product.quantity = 0.4
        first.action_post()
        second = self._reverse_invoice(
            invoice, reason="NC parcial 2", invoice_date=date_second
        )
        product2 = second.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        product2.quantity = 0.6
        second.action_post()
        company_cur = invoice.company_currency_id
        total_bs = company_cur.round(
            first._l10n_ve_to_company_abs_amount()
            + second._l10n_ve_to_company_abs_amount()
        )
        self.assertEqual(
            total_bs, company_cur.round(invoice._l10n_ve_to_company_abs_amount())
        )
        self.assertEqual(first.invoice_currency_rate, invoice.invoice_currency_rate)
        self.assertEqual(second.invoice_currency_rate, invoice.invoice_currency_rate)

    def test_draft_refund_changing_invoice_date_keeps_origin_rate(self):
        date_invoice = fields.Date.to_date("2026-09-26")
        date_other = fields.Date.to_date("2026-09-28")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=830.0)
        self._ensure_usd_rate(date_other, inverse_company_rate=990.0)
        invoice = self._create_usd_invoice(date_invoice, (75.0, 25.0))
        credit = self._reverse_invoice(invoice, invoice_date=date_invoice)
        origin_rate = invoice.invoice_currency_rate
        origin_bs = self._company_base_amount(credit)
        credit.write(
            {
                "invoice_date": date_other,
                "invoice_date_due": date_other,
            }
        )
        self.assertEqual(credit.invoice_currency_rate, origin_rate)
        self.assertEqual(
            invoice.company_currency_id.round(self._company_base_amount(credit)),
            invoice.company_currency_id.round(origin_bs),
        )

    def test_ves_invoice_full_reversal_stays_ves(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "currency_id": self.ves.id,
                "invoice_date": fields.Date.to_date("2026-09-27"),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_iva_16.id,
                            "name": "Linea Bs",
                            "quantity": 1.0,
                            "price_unit": 10000.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set(self.iva_16.ids)],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        invoice.l10n_ve_invoice_original_printed = True
        credit = self._reverse_invoice(invoice)
        self.assertEqual(credit.currency_id, self.ves)
        self.assertEqual(credit.amount_untaxed, invoice.amount_untaxed)
        self.assertEqual(credit.amount_total, invoice.amount_total)
        credit.action_post()
        self.assertEqual(credit.state, "posted")

    def test_post_discount_usd_later_rate_document_stays_usd(self):
        date_invoice = fields.Date.to_date("2026-09-29")
        self._ensure_usd_rate(date_invoice, inverse_company_rate=770.0)
        self._ensure_usd_rate(fields.Date.today(), inverse_company_rate=920.0)
        invoice = self._create_usd_invoice(date_invoice, (100.0,))
        credit = self._apply_post_discount(invoice, mode="percentage", percentage=0.1)
        self.assertEqual(credit.currency_id, self.usd)
        self.assertAlmostEqual(credit.amount_untaxed, 10.0, places=2)
        expected_bs = invoice._l10n_ve_post_discount_amount_in_currency(
            10.0, invoice.company_currency_id
        )
        company_cur = invoice.company_currency_id
        self.assertAlmostEqual(
            company_cur.round(self._company_base_amount(credit)),
            company_cur.round(expected_bs),
            places=2,
        )
        later_bs = company_cur.round(10.0 * 920.0)
        self.assertNotAlmostEqual(
            company_cur.round(self._company_base_amount(credit)),
            later_bs,
            places=0,
        )
        credit.action_post()
        self.assertEqual(credit.state, "posted")
