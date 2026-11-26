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
        currency=None,
        product=None,
    ):
        vals = {
            "move_type": "out_invoice",
            "company_id": self.company.id,
            "journal_id": self.tfhka_journal.id,
            "partner_id": partner.id,
            "currency_id": (currency or self.usd).id,
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
                        "product_id": product.id if product else False,
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
            currency=self.ves,
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
            self.partner,
            self.revenue_account,
            price=10.004,
            quantity=1000.0,
            currency=self.ves,
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
            currency=self.ves,
        )
        count, total_discount, subtotal_before = (
            invoice._tfhka_line_discount_and_count()
        )
        self.assertEqual(count, 1)
        self.assertEqual(total_discount, 0.0)
        self.assertAlmostEqual(subtotal_before, invoice.invoice_line_ids.price_subtotal)

    def test_product_code_setting_and_currency_amounts(self):
        product = self.env["product.product"].create(
            {
                "name": "Producto TFHKA",
                "barcode": "7591234567890",
                "default_code": "REF-TFHKA",
            }
        )
        invoice = self._new_move(
            self.partner,
            self.revenue_account,
            price=100.0,
            product=product,
        )
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("l10n_ve_edi_tfhka.product_code", "default_code")
        detail = invoice._tfhka_build_item_detail(
            1,
            invoice.invoice_line_ids,
            "E",
            0.0,
            0.0,
            invoice._tfhka_get_line_price_breakdown(invoice.invoice_line_ids),
        )
        self.assertEqual(detail["codigoPLU"], "REF-TFHKA")
        icp.set_param("l10n_ve_edi_tfhka.product_code", "barcode")
        detail = invoice._tfhka_build_item_detail(
            1,
            invoice.invoice_line_ids,
            "E",
            0.0,
            0.0,
            invoice._tfhka_get_line_price_breakdown(invoice.invoice_line_ids),
        )
        self.assertEqual(detail["codigoPLU"], "7591234567890")

        currency = invoice.currency_id
        line = invoice.invoice_line_ids
        _unit, doc_subtotal, doc_total = invoice._tfhka_line_document_amounts(line)
        self.assertAlmostEqual(
            float(detail["precioItem"]), currency.round(doc_subtotal)
        )
        self.assertAlmostEqual(
            float(detail["valorTotalItem"]), currency.round(doc_total)
        )
        totals = invoice._tfhka_get_totals_for_payload()
        self.assertAlmostEqual(
            totals["inv"]["subtotal"], currency.round(doc_subtotal)
        )
        self.assertAlmostEqual(totals["inv"]["subtotal"], invoice.amount_untaxed)

    def _tfhka_usd_invoice(self, price, quantity=3.0, discount=0.2, lines=1):
        tax = self.company_data["default_tax_sale"]
        vals = {
            "move_type": "out_invoice",
            "company_id": self.company.id,
            "journal_id": self.tfhka_journal.id,
            "partner_id": self.partner.id,
            "currency_id": self.usd.id,
            "invoice_date": self.test_date,
            "date": self.test_date,
            "invoice_line_ids": [
                Command.create(
                    {
                        "name": f"Linea {index}",
                        "quantity": quantity,
                        "price_unit": price,
                        "discount": discount,
                        "account_id": self.revenue_account.id,
                        "tax_ids": [Command.set(tax.ids)],
                    }
                )
                for index in range(1, lines + 1)
            ],
        }
        return self.env["account.move"].with_company(self.company).create(vals)

    def test_totals_use_system_amounts_per_currency(self):
        """Bs come from ``totales``, the document currency from the invoice."""
        invoice = self._tfhka_usd_invoice(48.2559632467655, lines=8)
        payload = invoice._tfhka_build_documento_electronico_payload()
        doc = payload["documentoElectronico"]
        encabezado = doc["encabezado"]
        totales = encabezado["totales"]
        otra = encabezado["totalesOtraMoneda"]
        items = doc["detallesItems"]

        def amount(value):
            return float(str(value).replace(",", "."))

        self.assertEqual(
            encabezado["identificacionDocumento"]["moneda"],
            invoice.currency_id.name,
        )
        self.assertEqual(otra["moneda"], invoice.currency_id.name)
        self.assertAlmostEqual(
            amount(totales["subtotal"]), invoice.amount_untaxed_signed, delta=0.01
        )
        self.assertAlmostEqual(
            amount(totales["totalIVA"]), invoice.amount_tax_signed, delta=0.01
        )
        self.assertAlmostEqual(
            amount(totales["totalAPagar"]), invoice.amount_total_signed, delta=0.01
        )
        self.assertAlmostEqual(
            amount(otra["subtotal"]), invoice.amount_untaxed, delta=0.01
        )
        self.assertAlmostEqual(
            amount(otra["totalIVA"]), invoice.amount_tax, delta=0.01
        )
        self.assertAlmostEqual(
            amount(otra["totalAPagar"]), invoice.amount_total, delta=0.01
        )
        item_base = sum(amount(item["precioItem"]) for item in items)
        item_iva = sum(amount(item["valorIVA"]) for item in items)
        self.assertAlmostEqual(item_base, amount(otra["subtotal"]), places=2)
        self.assertAlmostEqual(item_iva, amount(otra["totalIVA"]), places=2)
        rate = amount(otra["tipoCambio"])
        self.assertGreater(rate, 0.0)
        self.assertAlmostEqual(
            amount(totales["subtotal"]), amount(otra["subtotal"]) * rate, delta=0.01
        )
        self.assertAlmostEqual(
            amount(totales["totalAPagar"]),
            amount(otra["totalAPagar"]) * rate,
            delta=0.01,
        )

    def test_company_rate_ratio_uses_account_currency_lines(self):
        """``tipoCambio`` must be the ratio of the line bolivar amounts."""
        invoice = self._tfhka_usd_invoice(48.2559632467655, lines=8)
        comp_cur = invoice.company_id.currency_id
        inv_cur = invoice.currency_id
        base_comp = comp_cur.round(
            sum(line.price_subtotal_currency for line in invoice.invoice_line_ids)
        )
        base_inv = inv_cur.round(
            sum(line.price_subtotal for line in invoice.invoice_line_ids)
        )
        self.assertAlmostEqual(
            invoice._tfhka_company_rate_ratio(),
            base_comp / base_inv,
            places=6,
        )

    def test_comprador_declares_the_full_address(self):
        """``direccion`` must be the complete Odoo address, not only street."""
        venezuela = self.env.ref("base.ve")
        state = (
            self.env["res.country.state"]
            .search([("code", "=", "LR"), ("country_id", "=", venezuela.id)], limit=1)
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Direcciones Test",
                "vat": "V11223344",
                "street": "AV LOS LEONES CON CALLE TEREPAIMA",
                "street2": "EDIF TORRE BEL PISO 17",
                "zip": "3001",
                "city": "Barquisimeto",
                "state_id": state.id if state else False,
                "country_id": venezuela.id,
            }
        )
        invoice = self._new_move(partner, self.revenue_account)
        comprador = invoice._tfhka_build_comprador()
        address = comprador["direccion"]
        for fragment in (
            "AV LOS LEONES CON CALLE TEREPAIMA",
            "EDIF TORRE BEL PISO 17",
            "Barquisimeto",
            "3001",
        ):
            self.assertIn(fragment, address)
        if state:
            self.assertIn(state.code, address)
        self.assertNotIn("Venezuela", address)
        self.assertNotIn("Direcciones Test", address)
        self.assertLessEqual(len(address), 255)

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
