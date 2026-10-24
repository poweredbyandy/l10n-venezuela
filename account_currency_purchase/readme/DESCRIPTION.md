Aligns purchase order TaxTotals company-currency amounts with the same per-line
rounding used on vendor bills (`round(subtotal / rate)` per line, then
aggregate), so the order footer matches the bill created at the same rate.
