Shows and keeps invoice amounts in the company currency when the invoice is
issued in another currency:

- Exchange rate of the invoice, its inverse rate and a warning with a
  *Recalcular tasa* button when the rate no longer matches the rate of the
  invoice date.
- Credit notes keep the exchange rate of the invoice they reverse.
- *Unit Price in Company Currency*, *Subtotal in Company Currency* and
  *Total in Company Currency* on every invoice line. The unit price is before
  discount. Subtotal and total are editable in draft: they keep the foreign
  amounts and adjust the line exchange rate so the company balance matches.
- Invoice totals widget with an extra column in the company currency.
- With `account_currency_sale` / `account_currency_purchase`, sale and purchase
  TaxTotals company amounts use the same per-line rounding as invoices/bills.
- Chatter on currencies and exchange rates. Changes of the rate are logged in
  the chatter of the exchange rate.
