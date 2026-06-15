**Objetivo de homologación**

La homologación ante el SENIAT exige que el software de facturación garantice
la integridad de los documentos fiscales, el control de correlativos, la
trazabilidad de anulaciones y el cumplimiento de reglas de negocio que eviten
emisión incorrecta de facturas, notas de crédito y notas de débito. Este
módulo incorpora dichas reglas como **validaciones automáticas** en el flujo
estándar de Odoo, de modo que el comportamiento del sistema pueda ser verificado
y demostrado durante las pruebas de homologación.

Las validaciones descritas a continuación están respaldadas por pruebas
automatizadas en `l10n_ve_seniat/tests/`.

**Validaciones por área**

**Contactos y datos fiscales**

- **Formato de RIF/CI**: validación del patrón venezolano
  (`V`, `E`, `J`, `C`, `P` o `G` seguido del número de identificación).
  Aplicable a clientes y proveedores venezolanos cuando la opción
  *Validar formato de RIF/CI* está activa.
- **Prefijo automático de RIF**: normalización al guardar contactos
  venezolanos.
- **Tipo de contribuyente**: obligatorio en contactos con país Venezuela.
- **Bloqueo de datos fiscales**: cuando está habilitado, impide modificar
  nombre y RIF de contactos que ya tienen movimientos contables publicados.
- **Municipios y parroquias**: catálogo local y restricción de unicidad por
  estado.

**Configuración de impuestos**

- **Alícuotas inmutables**: en compañías venezolanas no se permite modificar
  el porcentaje de impuestos ya creados; las alícuotas se referencian desde
  la configuración de la empresa (exento, general, reducido, extendido) para
  ventas y compras.
- **Un impuesto por línea**: al confirmar facturas de cliente o proveedor, cada
  línea solo puede tener un impuesto asignado.
- **Un impuesto por producto**: los productos deben tener exactamente un
  impuesto de venta y uno de compra; no se permiten múltiples impuestos del
  mismo tipo.

**Productos**

- **Precio de venta positivo**: no se permiten precios menores o iguales a
  cero en líneas de factura venezolanas.
- **Descuento del 100 %**: rechazado en líneas de factura (equivalente a
  precio cero).
- **Precio de venta vs. coste**: opcionalmente se exige que el precio de venta
  sea mayor o igual al coste estándar.

**Emisión de facturas de cliente**

- **RIF obligatorio**: el cliente venezolano debe tener RIF configurado para
  confirmar la factura.
- **Total distinto de cero**: no se permite confirmar facturas con importe
  total nulo.
- **Fecha de vencimiento**: no puede ser anterior a la fecha de la factura.
- **Medio de emisión** (configurado en el diario de ventas):
  - *Forma libre*: exige tramos de talonario configurados; asigna correlativo
    automático de número de control.
  - *Contingencia*: exige fecha del documento y número de control manual antes
    de confirmar; no usa correlativo del talonario.
  - *Máquina fiscal*: el número de control es manual; en facturación por cuenta
    de terceros es obligatorio.
  - *Facturación digital*: no exige número de control previo a la confirmación
    (la numeración la gestiona el flujo digital).
- **Impresión en forma libre**: control de acceso a PDF y notas de crédito/débito
  hasta que se imprima el original; soporte para PDF o papel continuo (ESC/P).
- **Fecha de proceso SENIAT**: registro automático al confirmar documentos
  fiscales.

**Talonarios (números de control)**

- **Integridad de tramos**: rangos numéricos coherentes, sin solapamiento ni
  huecos en correlativos.
- **Unicidad del número de control**: único por diario; no se permiten
  correlativos inferiores al último emitido.
- **Anulación de folios**: requiere motivo y queda registrada; el correlativo
  liberado no se reutiliza automáticamente.
- **Secuencias independientes** por tramo para facturas, notas de crédito y
  notas de débito.

**Notas de crédito y débito**

- **Documento origen obligatorio**: toda nota de crédito debe referenciar la
  factura afectada.
- **Motivo de anulación/reversión**: obligatorio al cancelar facturas o crear
  notas de crédito desde el asistente.
- **Límite acumulado**: las notas de crédito no pueden superar el total de la
  factura origen (incluyendo notas de débito asociadas).
- **Mismo diario que el origen**: las notas de crédito/débito deben usar el
  diario de la factura original.
- **Productos y descripciones**: validación de coherencia con la factura origen
  en notas de crédito.
- **Moneda extranjera**: conversión a moneda de la compañía cuando aplica,
  usando la tasa de la factura origen.
- **Bloqueo de borrador**: las facturas de cliente confirmadas no pueden volver
  a borrador (salvo contexto administrativo explícito).

**Facturación por cuenta de terceros**

- Debe estar habilitada en configuración de la compañía.
- El tercero venezolano debe tener RIF válido.
- Plazo de copia certificada calculado automáticamente según normativa.

**Tasas de cambio**

- **Bloqueo de modificación**: no se puede alterar una tasa de cambio si ya fue
  usada en facturas publicadas.
- **Alerta de tasa desactualizada** en borradores con moneda distinta a la de
  la compañía.

**Pagos y retenciones**

- Registro de **fecha de proceso** al validar pagos.
- Soporte de campo de retención en pagos (integración con módulos de
  retenciones).

**Guías de despacho no facturadas**

- Envío manual o programado de correo al destinatario configurado (por defecto
  SENIAT), con datos del implementador del sistema.
- Intervalo configurable y registro del último envío.

**Reportes e impresión**

- Formato de factura venezolano con datos fiscales, alícuotas y tasas.
- Nombre de archivo PDF según convención SENIAT.
- Control de visibilidad de acciones de impresión según medio de emisión y
  estado del documento.

**Trazabilidad para auditoría**

- Marca de versión del módulo en pantalla de inicio de sesión y sesión web.
- Dashboard de facturación en el tablero contable con indicadores del mes
  vigente.

**Alcance y módulos relacionados**

Este módulo cubre la base contable y fiscal SENIAT. Funcionalidades
complementarias de homologación se implementan en módulos hermanos del
repositorio, entre ellos:

- `l10n_ve_edi`: facturación digital.
- `l10n_ve_withholding`: retenciones de IVA e ISLR.
- `l10n_ve_igtf`: impuesto a las grandes transacciones financieras.
- `l10n_ve_stock`: guías de despacho e inventario fiscal.

La instalación conjunta de estos módulos permite completar el escenario de
pruebas exigido en un proceso integral de homologación.
