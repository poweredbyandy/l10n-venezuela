Aligns sale order TaxTotals company-currency amounts with the same per-line
rounding used on customer invoices (`round(subtotal / rate)` per line, then
aggregate), so the order footer matches the invoice created at the same rate.
