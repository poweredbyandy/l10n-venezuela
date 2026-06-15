**Emisión de facturas**

1. Cree la factura de cliente en el diario configurado.
2. Verifique cliente, RIF, líneas con un solo impuesto cada una y total > 0.
3. En **contingencia** o **máquina fiscal**, ingrese el número de control antes
   de confirmar.
4. Confirme la factura. El sistema asignará correlativo (forma libre) o validará
   el control manual según el medio de emisión.
5. Imprima el original (forma libre PDF o continuo) cuando corresponda.

**Notas de crédito y débito**

- Use el asistente de reversión o nota de débito indicando el **motivo**.
- La nota de crédito debe referenciar la factura origen.
- El total acumulado de notas de crédito no puede superar el de la factura.
- Use el mismo diario de la factura original.

**Cancelación de facturas**

Al cancelar una factura de cliente, el sistema solicita un **motivo de
anulación** registrado para auditoría SENIAT.

**Dashboard de facturación**

En el tablero contable (**Contabilidad → Tablero**), el panel SENIAT muestra
indicadores del mes en curso:

- Facturas emitidas
- Notas de crédito
- Facturas vencidas sin cobrar
- Acceso rápido a listados filtrados
- Envío de guías de despacho no facturadas (si `l10n_ve_stock` está instalado)

**Verificación previa a homologación**

Antes de las pruebas ante el SENIAT, confirme:

- [ ] Compañía venezolana con plan de cuentas y alícuotas configuradas.
- [ ] Talonario y tramos creados con rangos autorizados.
- [ ] Diario de ventas con medio de emisión y tramos correctos.
- [ ] Contactos de prueba con RIF válido y tipo de contribuyente.
- [ ] Productos con un impuesto de venta y uno de compra.
- [ ] Flujo completo: factura → impresión → nota de crédito → anulación.
- [ ] Datos del implementador completos.
- [ ] (Opcional) Envío de guías no facturadas configurado.
