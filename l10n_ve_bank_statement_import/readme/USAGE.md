1. Instale el módulo `l10n_ve_bank_statement_import`.
2. Vaya a **Contabilidad → Configuración → Mapeos de importación**.
3. Seleccione el mapeo del banco (Mercantil, Bancaribe, BFC, Banesco,
   BDV, BNC, Binance u otro incluido) o cree uno con las columnas de su archivo.
   El TXT de movimientos del BNC (separado por tabulaciones) usa fecha
   y hora para ordenar los movimientos del mismo día.
4. Si el extracto no tiene cabecera, indique las filas iniciales a omitir.
5. Si el archivo incluye saldo inicial o final, indique fila y columna
   (número 1-based o letra, por ejemplo `E`).
6. Importe el archivo (CSV, XLS, XLSX, HTML o comprobante BDVenlínea)
   desde el diario bancario.

El módulo omite las filas de saldo inicial y saldo final para no
crearlas como movimientos. No se puede eliminar un extracto con
apuntes ya conciliados.

El Excel de Binance, «Historial de transacciones», se importa con el
mapeo **Binance - Historial de transacciones**. La cabecera está en la
fila 10 (`Tiempo`, `Cuenta`, `Operación`, `Moneda`, `Cambio`,
`Observación`). Todas las líneas entran en la moneda del diario; la
columna `Moneda` solo queda en la etiqueta del movimiento. Un valor
negativo en `Cambio` es una salida. Las transferencias entre Spot y
Funding también se importan.
