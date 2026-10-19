Plantilla de plan de cuentas `ve_sunaval` para Venezuela, basada en el plan
contable SUNAVAL.

- Las cuentas de movimiento son los códigos del plan que no tienen subcuentas
  (1.317 cuentas).
- Los códigos con subcuentas se crean como grupos contables (1.935 grupos), por
  lo que el balance se puede agrupar por cualquier nivel del plan.
- Incluye los impuestos de IVA 0 %, 8 %, 16 % y 31 % de venta y compra con los
  grupos de impuesto de `l10n_ve_seniat`. El débito fiscal va a
  `27281010100102` y el crédito fiscal a `27281010100101`.
- Incluye la posición fiscal Puerto Libre.
- Deja configuradas las cuentas de la compañía: diferencial cambiario
  (`532980107` / `432980107`), suspenso bancario (`186020100001`),
  transferencias de liquidez (`186030100001`), sobrantes y faltantes de caja,
  y los diarios Banco (`11301010101101`) y Efectivo (`111010100001`).
