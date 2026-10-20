1. Create an invoice in a currency other than the company currency.
2. The exchange rate of the invoice date is used. Below it, the inverse rate
   is shown.
3. The *Subtotal in Company Currency* column shows each line in the company
   currency. Edit it to force a different amount; the line turns red if its
   rate differs from the invoice rate. Click *Reset* to go back to the invoice
   rate.
4. The totals show an extra column with the amounts in the company currency.
   Line subtotals in company currency follow the rounded foreign amount. Tax
   stays as Odoo computes it.
5. If the rate of the invoice date changes while the invoice is in draft, a
   warning appears. Click *Recalcular tasa* to apply the current rate.
6. Upgrading the module realigns posted customer invoices in a foreign
   currency whose company-currency tax was converted from the rounded foreign
   tax. Those invoices are drafted and posted again with the native tax.
   Linked payments keep their amount and are reattached; they are not reset
   to draft.

To review the changes made to an exchange rate, open the rate and check its
chatter.
