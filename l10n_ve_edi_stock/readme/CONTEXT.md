Customer invoices and withholding vouchers do not need inventory.
Dispatch guides do: they use the SENIAT control number, the dispatch
guide report and the delivery data from `l10n_ve_stock`.

This module keeps that flow out of `l10n_ve_edi`, so a company that only
emits invoices can install digital invoicing without stock.
