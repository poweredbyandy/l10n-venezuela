**Configuración de la compañía**

Vaya a **Contabilidad → Configuración → Ajustes** y abra el bloque
**Venezuela - Tax Configuration**.

**Datos fiscales de la compañía**

| Campo | Descripción |
|-------|-------------|
| **Taxpayer Type** | Tipo de contribuyente de la empresa (ordinario, especial, etc.). |
| **Facturación por cuenta de terceros** | Habilita la emisión de facturas donde un tercero es el beneficiario fiscal. |
| **Validar formato de RIF/CI** | Activa la validación estricta del RIF en contactos y al confirmar facturas. |
| **Bloquear datos fiscales con movimientos** | Impide cambiar nombre y RIF de contactos con documentos publicados. |
| **Exigir precio de venta ≥ coste** | Rechaza productos cuyo precio de venta sea inferior al coste estándar. |

**Alícuotas de impuestos**

Asigne los impuestos de venta y compra que representan cada tipo de alícuota
según la normativa vigente:

- Exento
- General (16 % u otra según configuración)
- Reducido
- Extendido

Estos impuestos se usan en productos, reportes y cálculos fiscales. Una vez
creados en una compañía venezolana, **no se puede modificar su porcentaje**
desde la interfaz.

**Implementador del sistema**

Complete los datos del implementador (requeridos para comunicaciones con el
SENIAT, como el envío de guías de despacho no facturadas):

- Razón social
- RIF
- Correo electrónico

**Guías de despacho no facturadas**

Requiere el módulo `l10n_ve_stock` para el listado de guías pendientes.

| Campo | Descripción |
|-------|-------------|
| **Correo destinatario** | Por defecto `proveedores.sistemas@seniat.gob.ve`. |
| **Envío automático** | Activa el cron que envía el reporte periódicamente. |
| **Intervalo** | Frecuencia del envío automático (días, horas, etc.). |

El envío manual también está disponible desde el **dashboard de facturación**
en el tablero contable.

**Talonarios (números de control)**

Menú: **SENIAT → Talonarios** o **Contabilidad → Clientes → Talonarios (N° control)**.

1. Cree un **talonario** indicando el rango autorizado por el SENIAT
   (desde / hasta).
2. Defina uno o más **tramos** dentro del rango. Cada tramo tendrá su propia
   secuencia de correlativos.
3. Configure el formato de impresión (espaciado de cabecera, etc.) si aplica.

Reglas importantes:

- Los tramos no pueden solaparse ni dejar huecos en los correlativos emitidos.
- La anulación de un folio requiere motivo y no reutiliza el número automáticamente.
- Solo usuarios con permisos de administración de correlativos pueden modificar
  o eliminar registros de control.

**Diarios de ventas**

En **Contabilidad → Configuración → Diarios**, abra el diario de ventas y
vaya a la pestaña **SENIAT**.

**Medio de emisión**

| Valor | Comportamiento |
|-------|----------------|
| **Forma libre** | Asigna número de control desde el talonario. Requiere tramos configurados. |
| **Contingencia** | Número de control y fecha del documento manuales; no usa talonario. |
| **Máquina fiscal** | Número de control manual; integración con impresora fiscal. |
| **Facturación digital** | Sin correlativo previo; numeración gestionada por el flujo EDI. |

**Tramos del talonario (forma libre)**

Asigne los tramos para:

- Facturas de cliente (obligatorio en forma libre)
- Notas de crédito (obligatorio en forma libre)
- Notas de débito (opcional; si no se indica, usa el tramo de facturas)

**Impresión en forma libre**

- **PDF**: informe estándar de factura venezolana.
- **Papel continuo (ESC/P USB)**: requiere el módulo `l10n_ve_invoice_escp`.

Hasta imprimir el original en forma libre, el sistema bloquea la creación de
notas de crédito y débito asociadas.

**Límites por pedido**

Para medios distintos de forma libre, configure el máximo de líneas por factura
y por guía de despacho (valor por defecto: 10).

**Código de forma de pago fiscal**

En diarios de banco, caja o tarjeta, indique el código numérico (01–24) usado
por la máquina fiscal TFHKA al registrar pagos.

**Contactos**

En la ficha del contacto venezolano:

1. Indique el **RIF** con formato válido (ej. `J-12345678-9` o `V12345678`).
2. Seleccione el **tipo de contribuyente**.
3. Complete **estado**, **municipio** y **parroquia** en la dirección.

Para facturación por cuenta de terceros, cree el contacto del tercero con su
RIF y asígnelo en la factura.

**Productos**

1. Asigne **un impuesto de venta** y **un impuesto de compra** por producto.
2. Verifique que el precio de venta sea mayor que cero.
3. Si activó *Exigir precio de venta ≥ coste*, ajuste precios antes de vender.

Los productos nuevos sin impuestos reciben automáticamente la alícuota exenta
configurada en la compañía.
