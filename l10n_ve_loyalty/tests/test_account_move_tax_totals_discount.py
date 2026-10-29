# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged

from odoo.addons.l10n_ve_loyalty.tests.common import L10nVeLoyaltyCommon


@tagged("post_install", "-at_install")
class TestAccountMoveTaxTotalsGlobalDiscount(L10nVeLoyaltyCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner VE global discount",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J12345679",
            }
        )

    def _create_invoice(self, price_unit=100.0, quantity=1.0, discount=0.0):
        product = self._create_product(
            name="Product line",
            list_price=price_unit,
            taxes_id=[Command.set(self.company_data["default_tax_sale"].ids)],
        )
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": "Product line",
                            "quantity": quantity,
                            "price_unit": price_unit,
                            "discount": discount,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )

    def _get_discount_reason(self, name):
        Reason = self.env["l10n.ve.discount.reason"]
        reason = Reason.search([("name", "=", name)], limit=1)
        if not reason:
            reason = Reason.create({"name": name})
        return reason

    def _add_global_discount(
        self,
        move,
        name,
        amount,
        discount_type="fixed",
        discount_percentage=0.0,
    ):
        return self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move.id,
                "reason_id": self._get_discount_reason(name).id,
                "amount": amount,
                "discount_type": discount_type,
                "discount_percentage": discount_percentage,
            }
        )

    def test_sequential_percentage_then_fixed_discount(self):
        move = self._create_invoice(price_unit=1000.0)
        self.assertAlmostEqual(move.amount_untaxed, 1000.0, places=2)
        self._add_global_discount(
            move,
            "Descuento 50%",
            500.0,
            discount_type="percentage",
            discount_percentage=0.5,
        )
        self._add_global_discount(move, "Descuento fijo", 10.0)
        self.assertAlmostEqual(move.amount_untaxed, 490.0, places=2)
        tax_totals = move.tax_totals
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount_currency"], 510.0, places=2
        )
        lines = tax_totals["l10n_ve_global_discount_lines"]
        self.assertEqual(lines[0]["discount_type"], "percentage")
        self.assertAlmostEqual(lines[0]["discount_percentage"], 0.5, places=4)
        self.assertAlmostEqual(lines[0]["amount"], 500.0, places=2)
        self.assertAlmostEqual(lines[1]["amount"], 10.0, places=2)

    def test_fixed_discount_wizard_on_total_reduces_amount_total(self):
        move = self._create_invoice(price_unit=100.0)
        tax = self.company_data["default_tax_sale"]
        self.assertAlmostEqual(tax.amount, 16.0, places=2)
        self.assertAlmostEqual(move.amount_untaxed, 100.0, places=2)
        self.assertAlmostEqual(move.amount_total, 116.0, places=2)
        wizard = self.env["l10n.ve.account.move.discount.wizard"].create(
            {
                "move_id": move.id,
                "discount_mode": "amount",
                "amount_base": "total",
                "amount": 10.0,
                "reason_id": self._get_discount_reason("Desc total").id,
            }
        )
        wizard.action_apply_discount()
        self.assertAlmostEqual(move.amount_total, 106.0, places=2)
        discount = move.l10n_ve_global_discount_ids
        self.assertEqual(len(discount), 1)
        self.assertEqual(discount.amount_base, "total")
        self.assertAlmostEqual(discount.amount, 8.62, places=2)

    def test_fixed_discount_wizard_on_untaxed_keeps_subtotal_base(self):
        move = self._create_invoice(price_unit=100.0)
        wizard = self.env["l10n.ve.account.move.discount.wizard"].create(
            {
                "move_id": move.id,
                "discount_mode": "amount",
                "amount_base": "untaxed",
                "amount": 10.0,
                "reason_id": self._get_discount_reason("Desc subtotal").id,
            }
        )
        wizard.action_apply_discount()
        self.assertAlmostEqual(move.amount_untaxed, 90.0, places=2)
        self.assertAlmostEqual(move.amount_total, 104.4, places=2)
        self.assertEqual(move.l10n_ve_global_discount_ids.amount_base, "untaxed")
        self.assertAlmostEqual(move.l10n_ve_global_discount_ids.amount, 10.0, places=2)

    def test_only_one_percentage_global_discount_allowed(self):
        move = self._create_invoice()
        self._add_global_discount(
            move,
            "Descuento 10%",
            10.0,
            discount_type="percentage",
            discount_percentage=0.1,
        )
        with self.assertRaises(ValidationError):
            self._add_global_discount(
                move,
                "Descuento 20%",
                20.0,
                discount_type="percentage",
                discount_percentage=0.2,
            )

    def test_percentage_discount_updates_when_invoice_changes(self):
        move = self._create_invoice(price_unit=1000.0)
        discount = self._add_global_discount(
            move,
            "Descuento 50%",
            500.0,
            discount_type="percentage",
            discount_percentage=0.5,
        )
        move.invoice_line_ids[0].write({"price_unit": 2000.0})
        self.assertAlmostEqual(discount.amount, 1000.0, places=2)
        self.assertAlmostEqual(move.amount_untaxed, 1000.0, places=2)

    def test_tax_totals_shows_grouped_global_discount(self):
        move = self._create_invoice()
        self._add_global_discount(move, "Promoción", 10.0)
        tax_totals = move.tax_totals

        self.assertTrue(tax_totals["l10n_ve_show_global_discount"])
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount_currency"], 10.0, places=2
        )
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross_currency"], 100.0, places=2
        )
        self.assertAlmostEqual(tax_totals["base_amount_currency"], 90.0, places=2)
        self.assertEqual(len(tax_totals["l10n_ve_global_discount_lines"]), 1)
        self.assertAlmostEqual(move.amount_untaxed, 90.0, places=2)
        self.assertAlmostEqual(move.l10n_ve_amount_untaxed_gross, 100.0, places=2)
        self.assertAlmostEqual(move.l10n_ve_amount_discount, 10.0, places=2)
        self.assertAlmostEqual(move.amount_total, 104.4, places=2)

    def test_original_tax_totals_template_shows_global_discount(self):
        move = self._create_invoice()
        self._add_global_discount(move, "Promoción", 10.0)
        rendered = self.env["ir.ui.view"]._render_template(
            "account.document_tax_totals",
            {
                "currency": move.currency_id,
                "tax_totals": move.tax_totals,
            },
        )
        self.assertIn("o_l10n_ve_global_discount", rendered)
        self.assertIn("Descuento", rendered)
        self.assertLess(
            rendered.index("o_subtotal"),
            rendered.index("o_l10n_ve_global_discount"),
        )

    def test_tax_totals_groups_multiple_global_discounts(self):
        move = self._create_invoice(price_unit=200.0)
        self._add_global_discount(move, "Promo A", 10.0)
        self._add_global_discount(move, "Promo B", 20.0)
        tax_totals = move.tax_totals

        self.assertTrue(tax_totals["l10n_ve_show_global_discount"])
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount_currency"], 30.0, places=2
        )
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross_currency"], 200.0, places=2
        )
        self.assertAlmostEqual(tax_totals["base_amount_currency"], 170.0, places=2)
        self.assertEqual(len(tax_totals["l10n_ve_global_discount_lines"]), 2)
        self.assertAlmostEqual(move.amount_untaxed, 170.0, places=2)

    def test_tax_totals_without_global_discount(self):
        move = self._create_invoice()
        tax_totals = move.tax_totals

        self.assertFalse(tax_totals.get("l10n_ve_show_global_discount"))
        self.assertAlmostEqual(
            tax_totals.get("l10n_ve_global_discount_amount_currency", 0.0),
            0.0,
            places=2,
        )

    def test_line_discount_not_exposed_in_tax_totals(self):
        move = self._create_invoice(discount=10.0)
        tax_totals = move.tax_totals

        self.assertFalse(tax_totals.get("l10n_ve_show_global_discount"))
        self.assertFalse(tax_totals.get("l10n_ve_show_line_discount"))

    def test_line_price_subtotal_wo_discount(self):
        move = self._create_invoice(price_unit=100.0, quantity=2.0, discount=10.0)
        line = move.invoice_line_ids.filtered(
            lambda aml: aml.display_type == "product"
        )[:1]
        self.assertAlmostEqual(line.l10n_ve_price_subtotal_wo_discount, 200.0, places=2)
        self.assertAlmostEqual(line.price_subtotal, 180.0, places=2)
        self.assertAlmostEqual(line.l10n_ve_price_discount, 20.0, places=2)
        self.assertAlmostEqual(
            line.l10n_ve_price_subtotal_wo_discount_currency, 200.0, places=2
        )
        self.assertAlmostEqual(line.l10n_ve_price_discount_currency, 20.0, places=2)

    def test_global_discount_keeps_company_currency_subtotal_gross(self):
        company_currency = self.env.company.currency_id
        usd = self.env.ref("base.USD")
        foreign = usd if company_currency != usd else self.env.ref("base.EUR")
        foreign.write({"active": True})
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal)
        invoice_date = fields.Date.today()
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": invoice_date,
                "inverse_company_rate": 2.0,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "journal_id": journal.id,
                "currency_id": foreign.id,
                "invoice_date": invoice_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set([self.company_data["default_tax_sale"].id])
                            ],
                        }
                    )
                ],
            }
        )
        self._add_global_discount(move, "Promoción", 10.0)
        line = move.invoice_line_ids

        self.assertAlmostEqual(line.price_subtotal, 100.0, places=2)
        self.assertAlmostEqual(line.price_subtotal_currency, 200.0, places=2)
        self.assertAlmostEqual(line.price_unit_company_currency, 200.0, places=2)
        self.assertAlmostEqual(
            move.tax_totals["l10n_ve_subtotal_gross"], 200.0, places=2
        )
        self.assertAlmostEqual(
            move.tax_totals["l10n_ve_global_discount_amount"], 20.0, places=2
        )
        self.assertAlmostEqual(move.tax_totals["base_amount"], 180.0, places=2)

    def test_subtotal_gross_company_matches_sum_of_product_lines(self):
        """Footer company subtotal before discount equals sum of line Bs."""
        company_currency = self.env.company.currency_id
        usd = self.env.ref("base.USD")
        foreign = usd if company_currency != usd else self.env.ref("base.EUR")
        foreign.write({"active": True})
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal)
        invoice_date = fields.Date.today()
        self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", foreign.id),
                ("company_id", "=", self.env.company.id),
                ("name", "=", invoice_date),
            ]
        ).unlink()
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": invoice_date,
                "inverse_company_rate": 879.1225,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "journal_id": journal.id,
                "currency_id": foreign.id,
                "invoice_date": invoice_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "PW20TT",
                            "quantity": 32.0,
                            "price_unit": 4.473315,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set([self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "name": "T16EPR-U15",
                            "quantity": 32.0,
                            "price_unit": 2.09142,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set([self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                ],
            }
        )
        lines = move.invoice_line_ids
        self.assertAlmostEqual(sum(lines.mapped("price_subtotal")), 210.08, places=2)
        self._add_global_discount(
            move,
            "Descuento 20%",
            42.02,
            discount_type="percentage",
            discount_percentage=0.20,
        )
        tax_totals = move.tax_totals
        self.assertAlmostEqual(move.amount_untaxed, 168.06, places=2)
        self.assertAlmostEqual(move.amount_tax, 26.89, places=2)
        self.assertAlmostEqual(move.amount_total, 194.95, places=2)
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross_currency"], 210.08, places=2
        )
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount_currency"], 42.02, places=2
        )
        self.assertAlmostEqual(tax_totals["base_amount_currency"], 168.06, places=2)
        self.assertAlmostEqual(tax_totals["tax_amount_currency"], 26.89, places=2)
        self.assertAlmostEqual(tax_totals["total_amount_currency"], 194.95, places=2)
        expected_gross = company_currency.round(
            sum(lines.mapped("price_subtotal_currency"))
        )
        expected_base = company_currency.round(abs(move.amount_untaxed_signed))
        expected_tax = company_currency.round(abs(move.amount_tax_signed))
        expected_total = company_currency.round(abs(move.amount_total_signed))
        expected_discount = company_currency.round(expected_gross - expected_base)
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross"], expected_gross, places=2
        )
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount"], expected_discount, places=2
        )
        self.assertAlmostEqual(tax_totals["base_amount"], expected_base, places=2)
        self.assertAlmostEqual(tax_totals["tax_amount"], expected_tax, places=2)
        self.assertAlmostEqual(tax_totals["total_amount"], expected_total, places=2)

    def _ensure_sale_discount_product(self, name):
        if "sale_discount_product_id" not in self.env["res.company"]._fields:
            self.skipTest("sale_discount_product_id requires sale module")
        discount_product = self.env["product.product"].create(
            {
                "name": name,
                "type": "service",
                "list_price": 1.0,
                "company_id": self.env.company.id,
            }
        )
        self.env.company.sale_discount_product_id = discount_product
        return discount_product

    def test_product_discount_line_exposed_in_tax_totals(self):
        discount_product = self._ensure_sale_discount_product(
            "Producto descuento global"
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": discount_product.id,
                            "name": "Descuento promocional",
                            "quantity": 1.0,
                            "price_unit": -15.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                ],
            }
        )
        discount_line = move._l10n_ve_get_product_discount_lines()
        tax_totals = move.tax_totals
        self.assertAlmostEqual(discount_line.price_subtotal, -15.0, places=2)
        self.assertTrue(tax_totals["l10n_ve_show_global_discount"])
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount_currency"], 15.0, places=2
        )
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross_currency"], 100.0, places=2
        )
        self.assertAlmostEqual(tax_totals["base_amount_currency"], 85.0, places=2)
        self.assertEqual(len(tax_totals["l10n_ve_global_discount_lines"]), 1)
        self.assertEqual(
            tax_totals["l10n_ve_global_discount_lines"][0]["source"], "product_line"
        )
        self.assertEqual(
            tax_totals["l10n_ve_global_discount_lines"][0]["discount_type"],
            "percentage",
        )
        self.assertTrue(
            tax_totals["l10n_ve_global_discount_lines"][0]["discount_percentage"]
        )
        self.assertTrue(tax_totals.get("l10n_ve_global_discount_percentage"))

    def test_remove_product_discount_line_from_tax_totals_action(self):
        discount_product = self._ensure_sale_discount_product(
            "Producto descuento a remover"
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": discount_product.id,
                            "name": "Descuento",
                            "quantity": 1.0,
                            "price_unit": -10.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                ],
            }
        )
        discount_line = move._l10n_ve_get_product_discount_lines()
        self.assertTrue(discount_line)
        move.action_l10n_ve_remove_global_discount(discount_line.id)
        self.assertFalse(move._l10n_ve_get_product_discount_lines())
        self.assertFalse(move.tax_totals.get("l10n_ve_show_global_discount"))

    def test_remove_global_discount_updates_totals(self):
        move = self._create_invoice()
        self.assertAlmostEqual(move.amount_untaxed, 100.0, places=2)
        discount = self._add_global_discount(move, "Temporal", 15.0)
        self.assertAlmostEqual(move.amount_untaxed, 85.0, places=2)
        discount.unlink()
        self.assertAlmostEqual(move.amount_untaxed, 100.0, places=2)
        self.assertFalse(move.tax_totals.get("l10n_ve_show_global_discount"))

    def test_unlink_draft_invoice_with_percentage_global_discount(self):
        move = self._create_invoice()
        self._add_global_discount(
            move,
            "Porcentaje",
            10.0,
            discount_type="percentage",
            discount_percentage=0.1,
        )
        move_id = move.id
        move.unlink()
        self.assertFalse(self.env["account.move"].browse(move_id).exists())

    def test_global_discount_cannot_exceed_subtotal(self):
        move = self._create_invoice()
        with self.assertRaises(UserError):
            self._add_global_discount(move, "Exceso", 150.0)

    def test_global_discount_with_mixed_tax_and_untaxed_lines(self):
        company = self.env.company
        sale_tax = company.account_sale_tax_id
        exempt_tax = self.env["account.tax.group"]._l10n_ve_get_exent_sale_tax(company)
        product_taxed = self._create_product(
            name="Gravada",
            list_price=100.0,
            taxes_id=[Command.set(sale_tax.ids)],
        )
        product_exempt = self._create_product(
            name="Exenta",
            list_price=50.0,
            taxes_id=[Command.set(exempt_tax.ids)],
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product_taxed.id,
                            "name": "Gravada",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [Command.set(sale_tax.ids)],
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_exempt.id,
                            "name": "Exenta",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "tax_ids": [Command.set(exempt_tax.ids)],
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                        }
                    ),
                ],
            }
        )
        self.assertAlmostEqual(move.amount_untaxed, 150.0, places=2)
        self._add_global_discount(move, "Descuento", 15.0)
        self.assertAlmostEqual(move.amount_untaxed, 135.0, places=2)
        move.invoice_line_ids[0].write({"price_unit": 110.0})
        self.assertAlmostEqual(move.amount_untaxed, 145.0, places=2)

    def _create_foreign_invoice_with_percentage_discount(self):
        company_currency = self.env.company.currency_id
        usd = self.env.ref("base.USD")
        foreign = usd if company_currency != usd else self.env.ref("base.EUR")
        foreign.write({"active": True})
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal)
        invoice_date = fields.Date.today()
        self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", foreign.id),
                ("company_id", "=", self.env.company.id),
                ("name", "=", invoice_date),
            ]
        ).unlink()
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": invoice_date,
                "inverse_company_rate": 860.1753,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "journal_id": journal.id,
                "currency_id": foreign.id,
                "invoice_date": invoice_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Product line",
                            "quantity": 4.0,
                            "price_unit": 28.52,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set([self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                ],
            }
        )
        self.assertAlmostEqual(move.amount_untaxed, 114.08, places=2)
        self._add_global_discount(
            move,
            "Descuento 10%",
            11.41,
            discount_type="percentage",
            discount_percentage=0.10,
        )
        return move

    def test_new_foreign_invoice_company_totals_follow_accounting(self):
        move = self._create_foreign_invoice_with_percentage_discount()
        self.assertFalse(move.l10n_ve_legacy_company_discount_totals)
        tax_totals = move.tax_totals
        self.assertAlmostEqual(move.amount_untaxed, 102.67, places=2)
        self.assertAlmostEqual(move.amount_tax, 16.43, places=2)
        self.assertAlmostEqual(move.amount_total, 119.10, places=2)
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross_currency"], 114.08, places=2
        )
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount_currency"], 11.41, places=2
        )
        self.assertAlmostEqual(tax_totals["base_amount_currency"], 102.67, places=2)
        self.assertAlmostEqual(tax_totals["tax_amount_currency"], 16.43, places=2)
        self.assertAlmostEqual(tax_totals["total_amount_currency"], 119.10, places=2)
        company_currency = self.env.company.currency_id
        expected_gross = company_currency.round(
            sum(move.invoice_line_ids.mapped("price_subtotal_currency"))
        )
        expected_base = company_currency.round(abs(move.amount_untaxed_signed))
        expected_tax = company_currency.round(abs(move.amount_tax_signed))
        expected_total = company_currency.round(abs(move.amount_total_signed))
        expected_discount = company_currency.round(expected_gross - expected_base)
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross"], expected_gross, places=2
        )
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount"], expected_discount, places=2
        )
        self.assertAlmostEqual(tax_totals["base_amount"], expected_base, places=2)
        self.assertAlmostEqual(tax_totals["tax_amount"], expected_tax, places=2)
        self.assertAlmostEqual(tax_totals["total_amount"], expected_total, places=2)

    def test_percentage_discount_arithmetic_holds_in_both_currencies(self):
        company_currency = self.env.company.currency_id
        usd = self.env.ref("base.USD")
        foreign = usd if company_currency != usd else self.env.ref("base.EUR")
        foreign.write({"active": True})
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal)
        invoice_date = fields.Date.today()
        self.env["res.currency.rate"].search(
            [
                ("currency_id", "=", foreign.id),
                ("company_id", "=", self.env.company.id),
                ("name", "=", invoice_date),
            ]
        ).unlink()
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": invoice_date,
                "inverse_company_rate": 880.1159,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "journal_id": journal.id,
                "currency_id": foreign.id,
                "invoice_date": invoice_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Line A",
                            "quantity": 32.0,
                            "price_unit": 4.37437,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set([self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "name": "Line B",
                            "quantity": 32.0,
                            "price_unit": 2.04516,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set([self.company_data["default_tax_sale"].id])
                            ],
                        }
                    ),
                ],
            }
        )
        self.assertAlmostEqual(move.amount_untaxed, 205.43, places=2)
        self._add_global_discount(
            move,
            "Descuento 20%",
            41.09,
            discount_type="percentage",
            discount_percentage=0.20,
        )
        tax_totals = move.tax_totals
        self.assertAlmostEqual(move.amount_untaxed, 164.34, places=2)
        self.assertAlmostEqual(move.amount_tax, 26.29, places=2)
        self.assertAlmostEqual(move.amount_total, 190.63, places=2)
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross_currency"], 205.43, places=2
        )
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount_currency"], 41.09, places=2
        )
        self.assertAlmostEqual(tax_totals["base_amount_currency"], 164.34, places=2)
        self.assertAlmostEqual(tax_totals["tax_amount_currency"], 26.29, places=2)
        self.assertAlmostEqual(tax_totals["total_amount_currency"], 190.63, places=2)
        expected_gross = company_currency.round(
            sum(move.invoice_line_ids.mapped("price_subtotal_currency"))
        )
        expected_base = company_currency.round(abs(move.amount_untaxed_signed))
        expected_tax = company_currency.round(abs(move.amount_tax_signed))
        expected_total = company_currency.round(abs(move.amount_total_signed))
        expected_discount = company_currency.round(expected_gross - expected_base)
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross"], expected_gross, places=2
        )
        self.assertAlmostEqual(
            tax_totals["l10n_ve_global_discount_amount"], expected_discount, places=2
        )
        self.assertAlmostEqual(tax_totals["base_amount"], expected_base, places=2)
        self.assertAlmostEqual(tax_totals["tax_amount"], expected_tax, places=2)
        self.assertAlmostEqual(tax_totals["total_amount"], expected_total, places=2)
        move.action_post()
        self.assertAlmostEqual(move.amount_untaxed, 164.34, places=2)
        self.assertAlmostEqual(move.amount_tax, 26.29, places=2)
        self.assertAlmostEqual(move.amount_total, 190.63, places=2)

    def test_legacy_foreign_invoice_company_totals_follow_accounting(self):
        move = self._create_foreign_invoice_with_percentage_discount()
        move.l10n_ve_legacy_company_discount_totals = True
        copied = move.copy()
        self.assertFalse(copied.l10n_ve_legacy_company_discount_totals)
        tax_totals = move.tax_totals
        company_currency = self.env.company.currency_id
        expected_base = company_currency.round(abs(move.amount_untaxed_signed))
        expected_tax = company_currency.round(abs(move.amount_tax_signed))
        expected_total = company_currency.round(abs(move.amount_total_signed))
        self.assertAlmostEqual(tax_totals["base_amount"], expected_base, places=2)
        self.assertAlmostEqual(tax_totals["tax_amount"], expected_tax, places=2)
        self.assertAlmostEqual(tax_totals["total_amount"], expected_total, places=2)
        group_bases = sum(
            group["base_amount"]
            for subtotal in tax_totals["subtotals"]
            for group in subtotal["tax_groups"]
        )
        self.assertAlmostEqual(group_bases, expected_base, places=2)

    def test_foreign_invoice_without_discount_follows_tax_lines(self):
        move = self._create_foreign_invoice_with_percentage_discount()
        move.l10n_ve_global_discount_ids.unlink()
        tax_totals = move.tax_totals
        group = tax_totals["subtotals"][0]["tax_groups"][0]
        self.assertAlmostEqual(move.amount_untaxed, 114.08, places=2)
        self.assertAlmostEqual(
            tax_totals["l10n_ve_subtotal_gross_currency"], 114.08, places=2
        )
        self.assertAlmostEqual(tax_totals["base_amount_currency"], 114.08, places=2)
        self.assertAlmostEqual(group["base_amount"], 98128.80, places=2)
        self.assertAlmostEqual(tax_totals["base_amount"], 98128.80, places=2)
        self.assertAlmostEqual(group["tax_amount"], 15700.61, places=2)
        self.assertAlmostEqual(tax_totals["tax_amount"], 15700.61, places=2)


@tagged("post_install", "-at_install")
class TestAccountMoveGlobalDiscountJournalLines(L10nVeLoyaltyCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner VE discount journal",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J123456780",
            }
        )
        cls.discount_allocation_account = cls.env["account.account"].create(
            {
                "name": "VE Global discount allocation",
                "code": "VEDISCAL",
                "account_type": "expense",
                "company_ids": [(6, 0, cls.env.company.ids)],
            }
        )
        cls.env.company.account_discount_expense_allocation_id = (
            cls.discount_allocation_account
        )

    def _create_invoice(self, price_unit=100.0, quantity=1.0):
        product = self._create_product(
            name="Product line",
            list_price=price_unit,
            taxes_id=[Command.set(self.company_data["default_tax_sale"].ids)],
        )
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "name": "Product line",
                            "quantity": quantity,
                            "price_unit": price_unit,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                ],
            }
        )

    def _get_discount_reason(self, name):
        reason = self.env["l10n.ve.discount.reason"].search(
            [("name", "=", name)], limit=1
        )
        if not reason:
            reason = self.env["l10n.ve.discount.reason"].create({"name": name})
        return reason

    def _add_global_discount(self, move, name, amount):
        return self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move.id,
                "reason_id": self._get_discount_reason(name).id,
                "amount": amount,
            }
        )

    def test_global_discount_creates_accounting_discount_lines(self):
        revenue_account = self.company_data["default_account_revenue"]
        discount_account = self.discount_allocation_account

        move = self._create_invoice(price_unit=100.0)
        self._add_global_discount(move, "Promoción", 10.0)

        product_line = move.line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        global_discount_lines = move.line_ids.filtered("l10n_ve_global_discount_line")
        self.assertEqual(len(global_discount_lines), 1)
        self.assertEqual(product_line.account_id, revenue_account)
        self.assertAlmostEqual(product_line.amount_currency, -100.0, places=2)
        discount_line = global_discount_lines
        self.assertEqual(discount_line.account_id, discount_account)
        self.assertAlmostEqual(discount_line.amount_currency, 10.0, places=2)
        self.assertAlmostEqual(move.amount_untaxed, 90.0, places=2)
        self.assertAlmostEqual(move.tax_totals["base_amount_currency"], 90.0, places=2)
        self.assertAlmostEqual(
            move.tax_totals["l10n_ve_subtotal_gross_currency"], 100.0, places=2
        )

    def test_global_discount_accounting_lines_per_tax_group(self):
        revenue_account = self.company_data["default_account_revenue"]
        sale_tax = self.company_data["default_tax_sale"]
        exempt_tax = self.env["account.tax.group"]._l10n_ve_get_exent_sale_tax(
            self.env.company
        )

        product_taxed = self._create_product(
            name="Taxed product",
            list_price=100.0,
            taxes_id=[Command.set(sale_tax.ids)],
        )
        product_exempt = self._create_product(
            name="Exempt product",
            list_price=50.0,
            taxes_id=[Command.set(exempt_tax.ids)],
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product_taxed.id,
                            "name": "Taxed product",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(sale_tax.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_exempt.id,
                            "name": "Exempt product",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(exempt_tax.ids)],
                        }
                    ),
                ],
            }
        )
        self._add_global_discount(move, "Descuento mixto", 15.0)

        global_discount_lines = move.line_ids.filtered("l10n_ve_global_discount_line")
        subtotal_by_taxes = move._l10n_ve_global_discount_subtotal_by_taxes()
        self.assertEqual(len(global_discount_lines), len(subtotal_by_taxes))
        self.assertAlmostEqual(
            sum(line.amount_currency for line in global_discount_lines),
            15.0,
            places=2,
        )
        self.assertAlmostEqual(move.amount_untaxed, 135.0, places=2)
        self.assertAlmostEqual(move.tax_totals["base_amount_currency"], 135.0, places=2)
        self.assertAlmostEqual(
            move.tax_totals["l10n_ve_global_discount_amount_currency"], 15.0, places=2
        )
        self.assertAlmostEqual(
            move.tax_totals["l10n_ve_subtotal_gross_currency"], 150.0, places=2
        )

    def test_duplicate_invoice_with_global_discount_is_balanced(self):
        move = self._create_invoice(price_unit=100.0)
        self._add_global_discount(move, "Promoción", 10.0)
        self.assertTrue(move.line_ids.filtered("l10n_ve_global_discount_line"))

        duplicate = move.copy()

        self.assertEqual(len(duplicate.l10n_ve_global_discount_ids), 1)
        self.assertAlmostEqual(
            duplicate.l10n_ve_global_discount_ids.amount, 10.0, places=2
        )
        self.assertAlmostEqual(
            duplicate.tax_totals["l10n_ve_global_discount_amount_currency"],
            10.0,
            places=2,
        )
        self.assertTrue(duplicate.line_ids.filtered("l10n_ve_global_discount_line"))
        self.assertAlmostEqual(sum(duplicate.line_ids.mapped("balance")), 0.0, places=2)
        self.assertAlmostEqual(duplicate.amount_untaxed, 90.0, places=2)
        self.assertAlmostEqual(duplicate.amount_total, 104.4, places=2)

    def test_remove_global_discount_rebalances_invoice(self):
        move = self._create_invoice(price_unit=100.0)
        self._add_global_discount(move, "Promoción", 10.0)
        self.assertTrue(move.line_ids.filtered("l10n_ve_global_discount_line"))

        move.l10n_ve_global_discount_ids.unlink()

        self.assertFalse(move.l10n_ve_global_discount_ids)
        self.assertFalse(move.line_ids.filtered("l10n_ve_global_discount_line"))
        self.assertAlmostEqual(
            move.tax_totals.get("l10n_ve_global_discount_amount_currency", 0.0),
            0.0,
            places=2,
        )
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)

    def test_remove_global_discount_with_line_discount_rebalances_invoice(self):
        revenue_account = self.company_data["default_account_revenue"]
        sale_tax = self.company_data["default_tax_sale"]
        exempt_tax = self.env["account.tax.group"]._l10n_ve_get_exent_sale_tax(
            self.env.company
        )

        product_taxed = self._create_product(
            name="Taxed product",
            list_price=1000.0,
            taxes_id=[Command.set(sale_tax.ids)],
        )
        product_exempt = self._create_product(
            name="Exempt product",
            list_price=2000.0,
            taxes_id=[Command.set(exempt_tax.ids)],
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product_taxed.id,
                            "name": "Taxed product",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "discount": 3.99,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(sale_tax.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_exempt.id,
                            "name": "Exempt product",
                            "quantity": 1.0,
                            "price_unit": 2000.0,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(exempt_tax.ids)],
                        }
                    ),
                ],
            }
        )
        self._add_global_discount(move, "Promoción", 1500.0)
        self.assertTrue(move.line_ids.filtered("l10n_ve_global_discount_line"))
        self.assertFalse(move.line_ids.filtered("l10n_ve_line_discount_line"))

        move.l10n_ve_global_discount_ids.unlink()

        self.assertFalse(move.l10n_ve_global_discount_ids)
        self.assertFalse(move.line_ids.filtered("l10n_ve_global_discount_line"))
        self.assertFalse(move.line_ids.filtered("l10n_ve_line_discount_line"))
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)

    def test_line_and_global_discount_without_line_discount_journal_lines(self):
        revenue_account = self.company_data["default_account_revenue"]
        discount_account = self.discount_allocation_account
        sale_tax = self.company_data["default_tax_sale"]
        exempt_tax = self.env["account.tax.group"]._l10n_ve_get_exent_sale_tax(
            self.env.company
        )

        product_taxed = self._create_product(
            name="Taxed product",
            list_price=1000.0,
            taxes_id=[Command.set(sale_tax.ids)],
        )
        product_exempt = self._create_product(
            name="Exempt product",
            list_price=2000.0,
            taxes_id=[Command.set(exempt_tax.ids)],
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product_taxed.id,
                            "name": "Taxed product",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "discount": 3.99,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(sale_tax.ids)],
                        }
                    ),
                    Command.create(
                        {
                            "product_id": product_exempt.id,
                            "name": "Exempt product",
                            "quantity": 1.0,
                            "price_unit": 2000.0,
                            "account_id": revenue_account.id,
                            "tax_ids": [Command.set(exempt_tax.ids)],
                        }
                    ),
                ],
            }
        )
        self._add_global_discount(move, "Promoción", 1500.0)

        revenue_discount_lines = move.line_ids.filtered(
            lambda line: line.display_type == "discount"
            and line.account_id == revenue_account
        )
        line_discount_lines = move.line_ids.filtered("l10n_ve_line_discount_line")
        global_discount_lines = move.line_ids.filtered("l10n_ve_global_discount_line")
        taxed_product_line = move.line_ids.filtered(
            lambda line: line.display_type == "product" and line.name == "Taxed product"
        )

        self.assertFalse(revenue_discount_lines)
        self.assertFalse(line_discount_lines)
        self.assertTrue(global_discount_lines)
        self.assertAlmostEqual(taxed_product_line.amount_currency, -960.1, places=2)
        self.assertEqual(global_discount_lines.account_id, discount_account)
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)

    def test_global_discount_requires_permission(self):
        move = self._create_invoice(price_unit=100.0)
        invoice_user = self.env["res.users"].create(
            {
                "name": "Invoice user without discount",
                "login": "l10n_ve_invoice_no_discount",
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("account.group_account_invoice").id,
                        ]
                    )
                ],
            }
        )
        env = self.env(user=invoice_user)
        move_as_user = move.with_env(env)
        with self.assertRaises(UserError):
            move_as_user.action_l10n_ve_open_global_discount_wizard()
        with self.assertRaises(UserError):
            self.env["l10n.ve.account.move.discount"].with_env(env).create(
                {
                    "move_id": move.id,
                    "reason_id": self._get_discount_reason("Blocked").id,
                    "amount": 10.0,
                }
            )
        self.assertFalse(move_as_user.l10n_ve_show_global_discount_action)
        self.assertFalse(
            move_as_user.tax_totals.get("l10n_ve_can_manage_global_discount")
        )

    def _create_invoice_two_lines_with_percentage_discount(self):
        foreign_currency = self.setup_other_currency(
            "EUR", rates=[("2000-01-01", 1000.0)]
        )
        sale_tax = self.company_data["default_tax_sale"]
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "currency_id": foreign_currency.id,
                "invoice_date": fields.Date.from_string("2026-01-15"),
                "invoice_payment_term_id": self.env.ref(
                    "account.account_payment_term_immediate"
                ).id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self._create_product(
                                name=name,
                                list_price=price_unit,
                                taxes_id=[Command.set(sale_tax.ids)],
                            ).id,
                            "name": name,
                            "quantity": 1.0,
                            "price_unit": price_unit,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [Command.set(sale_tax.ids)],
                        }
                    )
                    for name, price_unit in (
                        ("First product", 100.0),
                        ("Second product", 50.0),
                    )
                ],
            }
        )
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move.id,
                "reason_id": self._get_discount_reason("Descuento 10%").id,
                "amount": 15.0,
                "discount_type": "percentage",
                "discount_percentage": 0.1,
            }
        )
        return move

    def _assert_global_discount_journal_items(self, move, gross, discount, total):
        product_lines = move.line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        discount_lines = move.line_ids.filtered("l10n_ve_global_discount_line")
        receivable_lines = move.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)
        self.assertAlmostEqual(
            sum(product_lines.mapped("amount_currency")), -gross, places=2
        )
        self.assertAlmostEqual(
            sum(discount_lines.mapped("amount_currency")), discount, places=2
        )
        self.assertAlmostEqual(
            sum(receivable_lines.mapped("amount_currency")), total, places=2
        )
        self.assertAlmostEqual(move.amount_total, total, places=2)

    def test_form_remove_line_keeps_global_discount_balanced(self):
        move = self._create_invoice_two_lines_with_percentage_discount()
        self._assert_global_discount_journal_items(move, 150.0, 15.0, 156.6)

        move_form = Form(move)
        move_form.invoice_line_ids.remove(index=1)
        move_form.save()

        self.assertAlmostEqual(
            move.l10n_ve_global_discount_ids.amount, 10.0, places=2
        )
        self._assert_global_discount_journal_items(move, 100.0, 10.0, 104.4)

    def test_form_edit_quantity_keeps_global_discount_balanced(self):
        move = self._create_invoice_two_lines_with_percentage_discount()

        move_form = Form(move)
        with move_form.invoice_line_ids.edit(0) as line_form:
            line_form.quantity = 2.0
        move_form.save()

        self.assertAlmostEqual(
            move.l10n_ve_global_discount_ids.amount, 25.0, places=2
        )
        self._assert_global_discount_journal_items(move, 250.0, 25.0, 261.0)
