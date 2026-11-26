from odoo import models

DELIVERY_CAMPO = "Direccion de Entrega"
NO_ADDRESS = "N/A"
FIELD_MAX_LENGTH = 255


class AccountMove(models.Model):
    _inherit = "account.move"

    def _tfhka_delivery_sale_orders(self):
        """Sale orders the document was invoiced from."""
        self.ensure_one()
        orders = self.line_ids.sale_line_ids.order_id
        if not orders and self.invoice_origin:
            orders = self.env["sale.order"].search(
                [
                    ("name", "=", self.invoice_origin),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
        return orders

    def _tfhka_delivery_addresses(self):
        """Delivery addresses that differ from the buyer fiscal address.

        TFHKA already receives the buyer domicile in ``comprador.direccion``,
        so the extra node is only useful when the goods go somewhere else.
        """
        self.ensure_one()
        if not self.is_sale_document(include_receipts=True):
            return []
        mixin = self.env["l10n_ve.edi.tfhka.document.mixin"]
        buyer_address = mixin._tfhka_get_partner_address(
            self._l10n_ve_edi_get_buyer_partner()
        ).casefold()
        addresses = []
        for partner in self._tfhka_delivery_sale_orders().mapped("partner_shipping_id"):
            address = mixin._tfhka_get_partner_address(partner)
            if address == NO_ADDRESS or address.casefold() == buyer_address:
                continue
            if address not in addresses:
                addresses.append(address)
        return addresses

    def _tfhka_build_info_adicional(self):
        """Add the delivery domicile to the ``infoAdicional`` node."""
        self.ensure_one()
        info_adicional = list(super()._tfhka_build_info_adicional())
        addresses = self._tfhka_delivery_addresses()
        if not addresses:
            return info_adicional
        info_adicional.append(
            {
                "campo": DELIVERY_CAMPO,
                "valor": " | ".join(addresses)[:FIELD_MAX_LENGTH],
            }
        )
        return info_adicional
