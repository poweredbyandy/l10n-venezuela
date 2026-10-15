Connector for The Factory HKA digital invoicing in Venezuela. It sends
customer invoices, credit and debit notes, dispatch guides and
withholding vouchers through the TFHKA API, stores the provider
response and serves the official digital PDF. It also queries the
numbering ranges available in TFHKA and assigns a new range when none
is available.

The payload follows the TFHKA API technical reference v2.2
(`static/description/tfhka_api_reference.pdf`), including IGTF debit
notes (transaction type 98) and buyers not domiciled in Venezuela.
