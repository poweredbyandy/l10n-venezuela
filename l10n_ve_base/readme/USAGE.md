En una compañía venezolana:

1. En **Contabilidad > Clientes > Facturas**, la factura muestra el número de
   control, los datos de máquina fiscal (serial, N° de factura y reporte Z),
   la fecha del documento y el contacto *por cuenta de terceros*. La lista
   agrega el número de control y, como columnas opcionales, los datos de
   máquina fiscal y la fecha del documento.
2. En **Contabilidad > Configuración > Grupos de impuestos**, cada grupo tiene
   su tipo de alícuota SENIAT.
3. En **Contabilidad > Configuración > Diarios**, el grupo **SENIAT** de
   la pestaña **Ajustes avanzados** de los diarios de ventas indica el medio
   de emisión.
4. En el formulario del contacto y de la compañía se indica el tipo de
   contribuyente.

Los datos de máquina fiscal solo aparecen si el diario de la factura usa el
medio **Máquina fiscal** y la factura no es por cuenta de terceros; se llenan
después de confirmar. El número de control se edita en borrador cuando el
diario usa contingencia o máquina fiscal, y es obligatorio con los medios que
no lo asignan automáticamente. La fecha del documento y el contacto por cuenta
de terceros dejan de ser editables al confirmar la factura. Con
`l10n_ve_seniat` instalado, el número de control además se muestra según el
talonario del diario.
