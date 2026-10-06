Comprobante de retención IVA y notas de débito
----------------------------------------------

1. Publique una factura o nota de débito de proveedor con retención IVA.
2. En el PDF del comprobante, la ND aparece en la columna **Nota de Débito**,
   el tipo de transacción es ``02-REG`` y **Factura afectada** muestra el
   número de la factura origen.
3. El TXT SENIAT de IVA usa el mismo criterio (tipo de documento ``02``).

Impresión y consulta de facturas afectadas
------------------------------------------

1. Abra una factura de proveedor que tenga una retención IVA o ISLR emitida.
2. Use el icono de impresora junto al número de comprobante para descargar el
   comprobante sin abrir primero la retención.
3. También puede abrir una retención emitida y usar el botón **Imprimir**.
4. En el listado de retenciones consulte las facturas afectadas.
5. En las líneas de la retención use el identificador mostrado y el icono de
   enlace para abrir directamente la factura correspondiente.

Las facturas afectadas se identifican priorizando el número de control, la
referencia del proveedor o el número de factura fiscal, seguido por el número
interno del asiento entre paréntesis.

Pago de retenciones de clientes desde el registro de pago
---------------------------------------------------------

1. En una factura de cliente publicada, pulse **Pagar** (Registrar pago).
2. Marque **Pago de retención**. Se habilita el campo **Tipo de retención**
   con las opciones **ISLR**, **IVA** y **Municipal**.
3. Al elegir el tipo se asigna el diario de retención de cliente que
   corresponde (el diario, el método de pago y el monto quedan bloqueados) y
   se cargan las líneas de retención de la factura:

   - **ISLR**: elija el concepto de pago e indique el monto retenido de cada
     línea.
   - **IVA**: el monto retenido se calcula solo (IVA de la factura por el
     porcentaje de retención del contacto).
   - **Municipal**: se propone la actividad económica del cliente (puede
     cambiarse) e indique el monto retenido de cada línea.

4. Indique la fecha y el número de comprobante (14 dígitos) y confirme.
5. Si desmarca **Pago de retención** (o cambia el tipo) se descartan el tipo,
   el comprobante y las líneas cargadas, y el pago vuelve a ser un pago normal.
