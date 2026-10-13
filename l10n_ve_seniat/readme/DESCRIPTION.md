Configuración contable SENIAT para Venezuela.

Incluye facturación fiscal, numeración, validaciones de RIF y el flujo de
notas de crédito y notas de débito tanto para facturas de cliente como de
proveedor (`out_invoice` / `in_invoice`).

Los descuentos globales y post-factura están en el módulo opcional `l10n_ve_loyalty`.

Los campos fiscales básicos (fecha del documento, número de control, datos de
máquina fiscal, por cuenta de terceros, alícuota del grupo de impuestos y tipo
de contribuyente) y sus vistas están en `l10n_ve_base`; este módulo agrega sus
validaciones, la visibilidad según el medio de emisión y los reportes.

Los planes de cuentas venezolanos, con sus impuestos, grupos de impuestos,
posiciones fiscales y la compañía demo, están en `l10n_ve_coa`. Ninguno de
los dos depende del otro; al
actualizarlo, si alguna compañía usa un plan SENIAT, la migración instala
`l10n_ve_coa` sin recargar el plan.

El medio de emisión (forma libre, contingencia, máquina fiscal o facturación
digital) se configura en cada diario de ventas. Los medios de una compañía son
los de sus diarios de ventas activos, y con ellos se muestran u ocultan los
menús y columnas que dependen del medio.

Los reportes nativos de facturas omiten el encabezado del diseño seleccionado.
El título muestra únicamente el nombre del documento y los totales omiten el
IGTF cuando el diario no tiene medio de emisión.
Los grupos de impuestos con una tasa de 0% no aparecen en los totales.

Los impuestos del producto son los nativos de Odoo (`taxes_id` y
`supplier_taxes_id`), con exactamente uno de venta y uno de compra por
compañía venezolana.

La fecha de recepción de la factura es el inicio de los plazos de pago y de
las cuotas de vencimiento.
