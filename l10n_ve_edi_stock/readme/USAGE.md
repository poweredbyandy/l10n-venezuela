1. Install `l10n_ve_edi_stock`. It is installed automatically when
   `l10n_ve_edi` and `l10n_ve_stock` are both installed.
2. Enable dispatch guides on the Venezuelan company and install the EDI
   connector of the sales journal.
3. Validate an outgoing picking that still needs a control number
   because the delivery is not fully invoiced.
4. Send the guide from the EDI tab on the picking.
5. Printing the local dispatch guide stays blocked until the EDI state
   is sent.
