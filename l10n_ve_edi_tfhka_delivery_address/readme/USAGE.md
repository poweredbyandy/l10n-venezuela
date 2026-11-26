1. Install `l10n_ve_edi_tfhka_delivery_address`.
2. Set a delivery address on the sale order (`partner_shipping_id`) that is
   different from the invoiced partner address.
3. Invoice the order and send it through TFHKA. The fiscal document shows
   `Direccion de Entrega` in its additional information.
