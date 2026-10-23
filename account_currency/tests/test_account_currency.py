# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import Form, tagged

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
        self.assertAlmostEqual(
            line.price_unit_company_currency * line.quantity,
            line.price_subtotal_currency,
            places=2,
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
