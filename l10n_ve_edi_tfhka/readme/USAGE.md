## Numbering ranges

1. Open a journal with provider **The Factory HKA** and click
   **Numeración TFHKA**. Only accounting administrators see the button.
2. Choose the document type. The serie comes from the journal and the
   proposed `numeroDocumento` range covers the selected month with the
   same format Odoo uses when emitting.
3. Click **Consultar** to see whether TFHKA has an available range.
4. Click **Consultar y asignar si no existe** to assign the range shown
   when TFHKA has none available. Nothing is assigned if a range
   already exists.

TFHKA rejects the assignment when the taxpayer has no control numbers
loaded. In that case ask The Factory HKA or your distributor to load a
batch of control numbers and assign the range again.

## Customer invoices

1. Confirm a customer invoice or credit note on a TFHKA journal.
2. Send the document from the EDI tab, or retry if the send failed.
3. When the state is sent, print or open the official TFHKA PDF.

## IGTF debit notes

1. Create a debit note from the invoice whose IGTF must be adjusted.
2. Book every line of the debit note on the company IGTF account, with
   the exempt sales tax.
3. Send it from the EDI tab. It is sent with transaction type 98 and
   the IGTF taxable base in USD and in bolivars.

## Customers outside Venezuela

Invoices and dispatch guides for a contact whose country is not
Venezuela send the foreign identification type set on the contact and
the tax ID without the country prefix. Sending is blocked until both
are set.

## Dispatch guides

1. Validate an outgoing picking that requires a SENIAT dispatch guide
   on a TFHKA sales journal.
2. Send the guide from the EDI tab.
3. Print is blocked until the EDI state is sent. The portal can show
   the official TFHKA PDF.

## Withholding vouchers

1. Emit an IVA or ISLR supplier withholding.
2. Send it from the EDI tab after the voucher has a number.
3. Print uses the official TFHKA PDF when the voucher was sent.
