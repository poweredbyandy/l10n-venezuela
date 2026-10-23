# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.l10n_ve_loyalty.tests.common import L10nVeLoyaltyCommon


@tagged("post_install", "-at_install")
class TestTaxTotalsManual(AccountTestInvoicingCommon):
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
        cls.env.user.write(
            {
                "groups_id": [
                    Command.link(
                        cls.env.ref(
                            "l10n_ve_tax_totals_manual.group_l10n_ve_tax_totals_manual"
                        ).id
                    )
                ]
            }
        )
        cls.env.registry.clear_cache()

    def _edit_tax_totals(self, invoice, kind, new_value, **extra):
        totals = dict(invoice.tax_totals)
        totals["manual_edit"] = {"kind": kind, "new_value": new_value, **extra}
        invoice.tax_totals = totals
        return invoice

    def _create_invoice(self):
        return self.init_invoice(
            "out_invoice",
            partner=self.partner_a,
            invoice_date=fields.Date.to_date("2024-01-10"),
            currency=self.foreign_currency,
            amounts=[100.0],
            taxes=self.env["account.tax"],
        )

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

    def test_manager_edits_document_and_company_base(self):
        invoice = self._create_invoice()
        self.assertTrue(invoice.tax_totals["can_edit_tax_totals"])
        self.assertTrue(invoice.l10n_ve_tax_totals_editable)
        subtotal_name = invoice.tax_totals["subtotals"][0]["name"]
        self._edit_tax_totals(
            invoice, "subtotal_currency", 80.0, subtotal_name=subtotal_name
        )
        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.price_subtotal, 80.0, places=2)
        self.assertAlmostEqual(abs(line.amount_currency), 80.0, places=2)
        self.assertAlmostEqual(abs(line.balance), 40.0, places=2)
        self.assertAlmostEqual(invoice.amount_total, 80.0, places=2)
        self.assertAlmostEqual(sum(invoice.line_ids.mapped("balance")), 0.0, places=2)

        self._edit_tax_totals(
            invoice, "subtotal_company", 55.0, subtotal_name=subtotal_name
        )
        self.assertAlmostEqual(abs(line.amount_currency), 80.0, places=2)
        self.assertAlmostEqual(abs(line.balance), 55.0, places=2)
        self.assertAlmostEqual(line.price_subtotal_currency, 55.0, places=2)
        self.assertAlmostEqual(invoice.amount_total, 80.0, places=2)
        self.assertAlmostEqual(abs(invoice.amount_untaxed_signed), 55.0, places=2)
        self.assertAlmostEqual(sum(invoice.line_ids.mapped("balance")), 0.0, places=2)
        receivable = invoice.line_ids.filtered(
            lambda move_line: move_line.display_type == "payment_term"
        )
        self.assertAlmostEqual(abs(receivable.balance), 55.0, places=2)
        self.assertAlmostEqual(abs(receivable.amount_currency), 80.0, places=2)

    def test_manager_edits_tax_company_and_total(self):
        tax = self._sale_percent_tax(16)
        invoice = self.init_invoice(
            "out_invoice",
            partner=self.partner_a,
            invoice_date=fields.Date.to_date("2024-01-10"),
            currency=self.foreign_currency,
            amounts=[100.0],
            taxes=tax,
        )
        tax_group = invoice.tax_totals["subtotals"][0]["tax_groups"][0]
        document_tax = tax_group["tax_amount_currency"]
        self._edit_tax_totals(
            invoice,
            "tax_company",
            10.0,
            tax_group_id=tax_group["id"],
        )
        tax_line = invoice.line_ids.filtered("tax_line_id")
        self.assertAlmostEqual(abs(sum(tax_line.mapped("balance"))), 10.0, places=2)
        self.assertAlmostEqual(
            abs(sum(tax_line.mapped("amount_currency"))), document_tax, places=2
        )
        self.assertAlmostEqual(sum(invoice.line_ids.mapped("balance")), 0.0, places=2)
        base = invoice.amount_untaxed
        self._edit_tax_totals(invoice, "total_currency", base + 3.0)
        self.assertAlmostEqual(invoice.amount_total, base + 3.0, places=2)
        self.assertAlmostEqual(invoice.amount_untaxed, base, places=2)
        self.assertAlmostEqual(sum(invoice.line_ids.mapped("balance")), 0.0, places=2)

    def test_edit_requires_manual_totals_group(self):
        self.assertTrue(
            self.env.ref("base.user_admin").has_group(
                "l10n_ve_tax_totals_manual.group_l10n_ve_tax_totals_manual"
            )
        )
        invoice = self._create_invoice()
        user = self.env["res.users"].create(
            {
                "name": "Billing user",
                "login": "billing_tax_totals_edit",
                "email": "billing_tax_totals_edit@example.com",
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("account.group_account_manager").id,
                        ]
                    )
                ],
            }
        )
        amount = invoice.amount_total
        edited = invoice.with_user(user)
        self.assertFalse(edited.tax_totals["can_edit_tax_totals"])
        self.assertFalse(edited.l10n_ve_tax_totals_editable)
        subtotal_name = edited.tax_totals["subtotals"][0]["name"]
        self._edit_tax_totals(
            edited, "subtotal_currency", 1.0, subtotal_name=subtotal_name
        )
        self.assertAlmostEqual(invoice.amount_total, amount, places=2)
        user.write(
            {
                "groups_id": [
                    Command.link(
                        self.env.ref(
                            "l10n_ve_tax_totals_manual.group_l10n_ve_tax_totals_manual"
                        ).id
                    )
                ]
            }
        )
        self.env.registry.clear_cache()
        edited = invoice.with_user(user)
        self.assertTrue(edited.tax_totals["can_edit_tax_totals"])
        self.assertTrue(edited.l10n_ve_tax_totals_editable)


@tagged("post_install", "-at_install")
class TestTaxTotalsManualDiscount(L10nVeLoyaltyCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner VE manual totals",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J22345679",
            }
        )
        discount_account = cls.env["account.account"].create(
            {
                "name": "VE manual discount allocation",
                "code": "VEMANDIS",
                "account_type": "expense",
                "company_ids": [Command.set(cls.env.company.ids)],
            }
        )
        cls.env.company.account_discount_expense_allocation_id = discount_account
        cls.env.user.write(
            {
                "groups_id": [
                    Command.link(
                        cls.env.ref(
                            "l10n_ve_tax_totals_manual.group_l10n_ve_tax_totals_manual"
                        ).id
                    )
                ]
            }
        )
        cls.env.registry.clear_cache()

    def test_discount_currency_becomes_fixed_untaxed(self):
        product = self._create_product(
            name="Product line",
            list_price=100.0,
            taxes_id=[Command.set(self.company_data["default_tax_sale"].ids)],
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "name": "Product line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set(self.company_data["default_tax_sale"].ids)
                            ],
                        }
                    )
                ],
            }
        )
        reason = self.env["l10n.ve.discount.reason"].search([], limit=1)
        if not reason:
            reason = self.env["l10n.ve.discount.reason"].create({"name": "Descuento"})
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move.id,
                "reason_id": reason.id,
                "amount": 10.0,
                "discount_type": "fixed",
            }
        )
        self.assertAlmostEqual(
            move.tax_totals["l10n_ve_global_discount_amount_currency"], 10.0, places=2
        )
        totals = dict(move.tax_totals)
        totals["manual_edit"] = {"kind": "discount_currency", "new_value": 15.0}
        move.tax_totals = totals
        self.assertAlmostEqual(
            move.tax_totals["l10n_ve_global_discount_amount_currency"], 15.0, places=2
        )
        self.assertEqual(move.l10n_ve_global_discount_ids.discount_type, "fixed")
        self.assertEqual(move.l10n_ve_global_discount_ids.amount_base, "untaxed")
        self.assertAlmostEqual(move.l10n_ve_global_discount_ids.amount, 15.0, places=2)
        discount_lines = move.line_ids.filtered("l10n_ve_global_discount_line")
        product_line = move.line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        self.assertAlmostEqual(
            abs(sum(discount_lines.mapped("amount_currency"))), 15.0, places=2
        )
        self.assertAlmostEqual(product_line.amount_currency, -100.0, places=2)
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)

    def test_company_gross_survives_discount_sync(self):
        foreign = self.setup_other_currency("EUR", rates=[("2016-01-01", 2.0)])
        product = self._create_product(
            name="Product line",
            list_price=100.0,
            taxes_id=[Command.set(self.company_data["default_tax_sale"].ids)],
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_ve.id,
                "currency_id": foreign.id,
                "invoice_date": fields.Date.to_date("2024-01-10"),
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "name": "Product line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set(self.company_data["default_tax_sale"].ids)
                            ],
                        }
                    )
                ],
            }
        )
        reason = self.env["l10n.ve.discount.reason"].search([], limit=1)
        if not reason:
            reason = self.env["l10n.ve.discount.reason"].create({"name": "Descuento"})
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move.id,
                "reason_id": reason.id,
                "amount": 10.0,
                "discount_type": "fixed",
            }
        )
        totals = dict(move.tax_totals)
        totals["manual_edit"] = {"kind": "gross_company", "new_value": 120.0}
        move.tax_totals = totals
        product_line = move.line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        self.assertAlmostEqual(abs(product_line.balance), 120.0, places=2)
        self.assertAlmostEqual(product_line.amount_currency, -100.0, places=2)
        self.assertAlmostEqual(
            move.tax_totals["l10n_ve_subtotal_gross"], 120.0, places=2
        )
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)
