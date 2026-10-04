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
        self.assertTrue(line.warning_rate_difference)
        self.assertTrue(line.has_rate_difference)
        self.assertTrue(invoice.lines_with_rate_difference)

        line.reset_price_subtotal_currency()
        self.assertFalse(line.manually_price_subtotal_currency)
        self.assertAlmostEqual(line.currency_rate, 2.0)
        self.assertAlmostEqual(line.price_subtotal_currency, 50.0)
        self.assertFalse(line.warning_rate_difference)
        self.assertFalse(invoice.lines_with_rate_difference)

    def test_company_currency_subtotal_updates_before_save(self):
        invoice = self._create_invoice()
        with Form(invoice) as move_form:
            with move_form.invoice_line_ids.edit(0) as line_form:
                line_form.price_unit = 300.0
                self.assertAlmostEqual(line_form.price_subtotal_currency, 150.0)
                self.assertFalse(line_form.manually_price_subtotal_currency)
        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.price_subtotal_currency, 150.0)
        self.assertAlmostEqual(abs(line.balance), 150.0)
        self.assertFalse(line.manually_price_subtotal_currency)

    def test_company_currency_subtotal_typed_in_form_is_manual(self):
        invoice = self._create_invoice()
        with Form(invoice) as move_form:
            with move_form.invoice_line_ids.edit(0) as line_form:
                line_form.price_subtotal_currency = 40.0
                self.assertTrue(line_form.manually_price_subtotal_currency)
        line = invoice.invoice_line_ids
        self.assertAlmostEqual(line.price_subtotal_currency, 40.0)
        self.assertAlmostEqual(line.currency_rate, 2.5)

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
