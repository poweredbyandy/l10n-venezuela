from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestTfhkaDeliveryInfoAdicional(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.venezuela = cls.env.ref("base.ve")
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Comprador Fiscal",
                "vat": "V12345678",
                "street": "AV PRINCIPAL DE LAS ACACIAS",
                "city": "Caracas",
                "zip": "1050",
                "country_id": cls.venezuela.id,
            }
        )
        cls.warehouse_partner = cls.env["res.partner"].create(
            {
                "name": "Deposito Logistico",
                "street": "UTA 74 CALLE C.C. TOTAL STOP",
                "city": "San Cristobal",
                "zip": "5001",
                "country_id": cls.venezuela.id,
            }
        )
        cls.order = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "partner_shipping_id": cls.warehouse_partner.id,
            }
        )
        cls.invoice = cls.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": cls.partner.id,
                "invoice_origin": cls.order.name,
            }
        )

    def _delivery_entries(self):
        return {
            info["campo"]: info["valor"]
            for info in self.invoice._tfhka_build_info_adicional()
        }

    def test_delivery_address_is_declared(self):
        entries = self._delivery_entries()
        self.assertIn("Direccion de Entrega", entries)
        valor = entries["Direccion de Entrega"]
        for fragment in ("UTA 74 CALLE C.C. TOTAL STOP", "San Cristobal", "5001"):
            self.assertIn(fragment, valor)
        self.assertNotIn("Venezuela", valor)
        self.assertNotIn("Deposito Logistico", valor)
        self.assertLessEqual(len(valor), 255)

    def test_same_address_as_buyer_is_not_declared(self):
        self.order.partner_shipping_id = self.partner
        self.assertNotIn("Direccion de Entrega", self._delivery_entries())

    def test_unknown_sale_order_is_not_declared(self):
        self.invoice.invoice_origin = "S0009999"
        self.assertFalse(self.invoice._tfhka_delivery_sale_orders())
        self.assertNotIn("Direccion de Entrega", self._delivery_entries())

    def test_address_without_domicile_is_not_declared(self):
        self.order.partner_shipping_id = self.env["res.partner"].create(
            {"name": "Sin Direccion", "country_id": self.venezuela.id}
        )
        self.assertNotIn("Direccion de Entrega", self._delivery_entries())

    def test_purchase_document_is_not_declared(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.warehouse_partner.id,
                "invoice_origin": self.order.name,
            }
        )
        self.assertEqual(bill._tfhka_delivery_addresses(), [])
