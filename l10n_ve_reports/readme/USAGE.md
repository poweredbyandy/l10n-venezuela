En el **Libro de Ventas** y el **Libro de Compras**, la base y el IVA de
cada alícuota salen de las líneas de impuesto del asiento publicado
(`tax_base_amount` y el saldo). Los documentos en borrador no entran al
libro. Así el periodo coincide con lo contabilizado y con lo impreso.
Al actualizar el módulo, las facturas ya publicadas alinean
`tax_base_amount` con la base en moneda compañía que ya mostraba
`tax_totals`. No se republica ni se toca el cobro. El IVA del libro
sigue siendo el del apunte, no el 16 % recalculado sobre la base.

To generate the auxiliary liquidity books:

#. Go to **Accounting > SENIAT > Reports**.
#. Open **Libro de Banco** or **Libro de Caja**.
#. Select the date range and, if needed, filter the bank or cash journals.
#. Review the chronological movements with opening balance, debits, credits, and running balance per account.
#. Export the report to PDF or XLSX using the standard report actions.

Each book only includes posted movements on the default liquidity account of the selected journals.

To review receivables and payables by journal:

#. Open **🇻🇪 Aged Receivable** or **🇻🇪 Aged Payable**.
#. Use the **Journals** filter to select one or more journals.
#. The aging buckets and the audit of each cell only include items from the selected journals. With no journal selected, all journals are included.

To review payments:

#. Go to **Accounting > SENIAT > Reports**.
#. Open **Reporte X** to review incoming and outgoing payments consolidated by payment method. The totals include registered bank movements and pending payments still on outstanding or bridge accounts.
#. Open **Pagos por diario** to review totals by journal and payment method.
#. Expand a payment method to display its registered and pending transactions, or collapse it to display only its consolidated total.
#. Review **Ingresos** and **Egresos** as fixed sections. Each section lists its payment methods (for example **Pago móvil** under income and **Transferencia** under expense). Only payment methods can be expanded or collapsed. The **Total** line remains the net of both.
#. Review **Facturas a crédito** after the **Total** line. It lists the posted customer invoices and vendor bills dated in the report period that are still unpaid or partially paid, under the informative payment method **Crédito**. Customer documents appear under **Ingresos** and vendor documents under **Egresos**. The **Total crédito** line is not added to the report **Total**.
#. A withholding that only settles the tax keeps the invoice on credit. The amount adds that withholding back, so the tax payment does not reduce the credit figure. A real payment does reduce it.
#. Open **Options** and uncheck **Facturas a crédito** to hide that section. It is shown by default.
