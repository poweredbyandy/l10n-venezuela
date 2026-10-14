In Venezuela, card terminals (puntos de venta) do not credit each sale
separately. At the end of the day the terminal runs a closing (cierre de
lote) and the bank deposits the total as a single transaction.

Odoo ends up with many payments (one per sale or per POS session) and
only one bank line, which makes bank reconciliation slow and error
prone. This module turns those payments into a single traceable item
that matches the bank transaction one to one.
