Con la factura en borrador, un usuario del grupo **Editar totales de la
factura** ve un lápiz en cada monto del bloque de totales. El administrador
lo trae activo.

- La base y el subtotal bruto en moneda del documento cambian el precio de las
  líneas de producto.
- La base y el subtotal bruto en moneda de la compañía cambian el balance de
  esas líneas y no tocan el monto en moneda del documento.
- El impuesto en moneda del documento sigue el lápiz nativo de Odoo.
- El impuesto en moneda de la compañía cambia el balance del apunte de
  impuesto.
- El total se consigue moviendo el impuesto. Si la factura no tiene impuesto,
  se mueve la base.
- El descuento global queda como monto fijo sin impuesto por el importe
  escrito.
- Si después se cambia el precio, la cantidad o el descuento de una línea, el
  ajuste manual de la compañía se suelta y el monto vuelve a convertirse con
  la tasa de la factura.
