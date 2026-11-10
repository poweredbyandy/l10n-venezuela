1. Install `l10n_ve_edi_stock_tfhka`. It is installed automatically when
   `l10n_ve_edi_stock` and `l10n_ve_edi_tfhka` are both installed.
2. Validate an outgoing picking that requires a SENIAT dispatch guide
   on a TFHKA sales journal.
3. Send the guide from the EDI tab.
4. Print stays blocked until the EDI state is sent. The portal can show
   the official TFHKA PDF.
5. When the related customer invoice is sent, the guide payload is
   updated with that invoice.

Guides for a contact whose country is not Venezuela send the foreign
identification type set on the contact and the tax ID without the
country prefix. Sending is blocked until both are set.
