Otros módulos necesitan leer o guardar los datos fiscales venezolanos de una
factura, un grupo de impuestos o un contacto sin cargar todas las reglas de
`l10n_ve_seniat`. Este módulo reúne solo esos campos para que puedan depender
de algo pequeño y estable.

Los campos venían de `l10n_ve_seniat`. Al instalar este módulo sus
identificadores pasan a `l10n_ve_base`, así que los valores guardados y el
historial de seguimiento se conservan.
