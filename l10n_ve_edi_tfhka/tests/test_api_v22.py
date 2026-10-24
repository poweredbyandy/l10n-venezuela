from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_ve_igtf.tests.common import TestL10nVeIgtfCommon


@tagged("post_install", "-at_install")
class TestTfhkaApiV22(TestL10nVeIgtfCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company.partner_id.write({"vat": "J123456789"})
        cls.tfhka_journal = (
            cls.env["account.journal"]
            .with_company(cls.company)
            .create(
                {
                    "name": "Ventas digital TFHKA",
                    "code": "VTFH",
                    "type": "sale",
                    "l10n_ve_emission_medium": "digital",
                    "l10n_ve_edi_provider": "tfhka",
                }
            )
        )
        cls.foreign_partner = cls.env["res.partner"].create(
            {
                "name": "Cliente Colombia",
                "vat": "CO900123456-8",
                "country_id": cls.env.ref("base.co").id,
                "l10n_ve_edi_tfhka_foreign_id_type": "nit",
            }
        )

    def _new_move(
        self,
        partner,
        line_account,
        origin=False,
        price=30.0,
        quantity=1.0,
        discount=0.0,
    ):
        vals = {
            "move_type": "out_invoice",
            "company_id": self.company.id,
            "journal_id": self.tfhka_journal.id,
            "partner_id": partner.id,
            "currency_id": self.usd.id,
            "invoice_date": self.test_date,
            "date": self.test_date,
            "invoice_line_ids": [
                Command.create(
                    {
                        "name": "Line",
                        "quantity": quantity,
                        "price_unit": price,
                        "discount": discount,
                        "account_id": line_account.id,
                        "tax_ids": [Command.set(self.exempt_sale_tax.ids)],
                    }
                )
            ],
        }
        if origin:
            vals["debit_origin_id"] = origin.id
        return self.env["account.move"].with_company(self.company).create(vals)

    def test_igtf_debit_note_uses_transaction_98(self):
        invoice = self._new_move(self.partner, self.revenue_account, price=1000.0)
        debit_note = self._new_move(self.partner, self.igtf_account, origin=invoice)
        self.assertTrue(debit_note._tfhka_is_igtf_debit_note())
        self.assertEqual(debit_note._tfhka_get_tipo_transaccion(), "98")
        self.assertEqual(
            debit_note._tfhka_get_igtf_debit_note_totals(),
            {"totalIGTF": "1000.00", "totalIGTF_VES": "438210.00"},
        )

    def test_regular_debit_note_keeps_transaction_02(self):
        invoice = self._new_move(self.partner, self.revenue_account, price=1000.0)
        debit_note = self._new_move(self.partner, self.revenue_account, origin=invoice)
        self.assertFalse(debit_note._tfhka_is_igtf_debit_note())
        self.assertEqual(debit_note._tfhka_get_tipo_transaccion(), "02")

    def test_invoice_with_igtf_account_is_not_debit_note(self):
        invoice = self._new_move(self.partner, self.igtf_account)
        self.assertFalse(invoice._tfhka_is_igtf_debit_note())
        self.assertEqual(invoice._tfhka_get_tipo_transaccion(), "01")

    def test_foreign_buyer_identification(self):
        invoice = self._new_move(self.foreign_partner, self.revenue_account)
        self.assertEqual(
            invoice._l10n_ve_edi_get_buyer_identification(), ("NIT", "9001234568")
        )
        invoice._l10n_ve_edi_validate_parties_identification()
        comprador = invoice._tfhka_build_comprador()
        self.assertEqual(comprador["tipoIdentificacion"], "NIT")
        self.assertEqual(comprador["pais"], "CO")

    def test_foreign_buyer_requires_identification_type(self):
        self.foreign_partner.l10n_ve_edi_tfhka_foreign_id_type = False
        invoice = self._new_move(self.foreign_partner, self.revenue_account)
        with self.assertRaises(UserError):
            invoice._l10n_ve_edi_validate_parties_identification()

    def test_line_price_breakdown_uses_declared_unit_price(self):
        invoice = self._new_move(
            self.partner,
            self.revenue_account,
            price=32.765795,
            quantity=3000.0,
            discount=13.75,
        )
        line = invoice.invoice_line_ids
        breakdown = invoice._tfhka_get_line_price_breakdown(line)
        self.assertEqual(breakdown["unit_price"], 32.77)
        self.assertAlmostEqual(breakdown["before_discount"], 98310.0)
        self.assertAlmostEqual(breakdown["subtotal"], line.price_subtotal)
        self.assertAlmostEqual(
            breakdown["before_discount"] - breakdown["discount"],
            breakdown["subtotal"],
        )

    def test_line_price_breakdown_never_declares_negative_discount(self):
        invoice = self._new_move(
            self.partner, self.revenue_account, price=10.004, quantity=1000.0
        )
        line = invoice.invoice_line_ids
        breakdown = invoice._tfhka_get_line_price_breakdown(line)
        self.assertEqual(breakdown["unit_price"], 10.01)
        self.assertGreaterEqual(breakdown["discount"], 0.0)
        self.assertAlmostEqual(
            breakdown["before_discount"] - breakdown["discount"],
            breakdown["subtotal"],
        )

    def test_line_discount_is_not_global_discount(self):
        invoice = self._new_move(
            self.partner,
            self.revenue_account,
            price=32.765795,
            quantity=3000.0,
            discount=13.75,
        )
        count, total_discount, subtotal_before = (
            invoice._tfhka_line_discount_and_count()
        )
        self.assertEqual(count, 1)
        self.assertEqual(total_discount, 0.0)
        self.assertAlmostEqual(subtotal_before, invoice.invoice_line_ids.price_subtotal)

    def test_resend_throttle_code_is_an_error(self):
        client = self.env["l10n_ve_edi_tfhka.api.service"]
        response = {
            "codigo": "99",
            "mensaje": "Su documento ya ha sido enviado previamente, "
            "favor de intentarlo mas tarde",
        }
        with self.assertRaises(UserError):
            client._raise_for_api_code(response)

    def test_venezuelan_buyer_keeps_rif(self):
        invoice = self._new_move(self.partner, self.revenue_account)
        self.assertEqual(
            invoice._l10n_ve_edi_get_buyer_identification(), ("V", "12345678")
        )
