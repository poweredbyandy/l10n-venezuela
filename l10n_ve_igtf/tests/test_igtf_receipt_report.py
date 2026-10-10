from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestL10nVeIgtfCommon


@tagged("post_install", "-at_install")
class TestIgtfReceiptReport(TestL10nVeIgtfCommon):
    def _pay_usd_invoice_with_igtf(self):
        invoice = self._create_customer_invoice(amount=1000.0, currency=self.usd)
        payment = self._register_invoice_payment(
            invoice=invoice,
            amount=1000.0,
            currency=self.usd,
            apply_igtf=True,
            igtf_included=False,
        )
        return invoice, payment

    def test_receipt_values_match_posted_igtf_line(self):
        invoice, payment = self._pay_usd_invoice_with_igtf()
        igtf_line = self._get_payment_igtf_line(payment)
        values = payment._l10n_ve_igtf_get_receipt_values()

        self.assertAlmostEqual(
            values["igtf_amount_company"], abs(igtf_line.balance), places=2
        )
        self.assertAlmostEqual(
            values["igtf_amount_currency"], abs(igtf_line.amount_currency), places=2
        )
        self.assertAlmostEqual(values["rate"], self.usd_inverse_rate, places=2)
        self.assertAlmostEqual(values["base_amount_currency"], 1000.0, places=2)
        self.assertEqual(values["long_date"], "Jueves 12 de marzo del 2026")
        self.assertEqual(len(values["documents"]), 1)
        self.assertEqual(values["documents"][0]["move"], invoice)
        self.assertEqual(values["documents"][0]["type"], "FAC")

    def test_receipt_amount_in_words(self):
        payment_model = self.env["account.payment"]
        self.assertEqual(
            payment_model._l10n_ve_igtf_receipt_amount_in_words(4055.29),
            "Cuatro Mil Cincuenta y Cinco Con 29/100",
        )
        self.assertEqual(
            payment_model._l10n_ve_igtf_receipt_amount_in_words(1000.0),
            "Mil Con 00/100",
        )

    def test_receipt_renders_pdf_html(self):
        invoice, payment = self._pay_usd_invoice_with_igtf()
        html = (
            self.env["ir.actions.report"]
            ._render_qweb_html("l10n_ve_igtf.report_igtf_receipt", payment.ids)[0]
            .decode()
        )
        self.assertIn("COMPROBANTE DE PERCEPCIÓN DEL IGTF", html)
        self.assertIn(payment.name, html)
        self.assertIn(invoice.name, html)
        self.assertIn(self.partner.name, html)

    def test_receipt_requires_igtf(self):
        invoice = self._create_customer_invoice(amount=100.0, currency=self.ves)
        payment = self._register_invoice_payment(
            invoice=invoice,
            amount=100.0,
            currency=self.ves,
        )
        with self.assertRaises(UserError):
            payment._l10n_ve_igtf_get_receipt_values()
