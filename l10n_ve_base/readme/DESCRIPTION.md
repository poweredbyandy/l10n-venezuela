Campos fiscales venezolanos mínimos y sus vistas:

- **Facturas** (`account.move`): fecha del documento, número de control,
  serial de máquina fiscal, número de factura fiscal, número de reporte Z,
  contacto *por cuenta de terceros* y su indicador calculado. Se muestran en
  el formulario y en la lista de facturas.
- **Grupos de impuestos** (`account.tax.group`): tipo de alícuota SENIAT
  (exento, general, reducida y adicional), en el formulario y en la lista.
- **Diarios** (`account.journal`): medio de emisión (forma libre,
  contingencia, máquina fiscal o facturación digital), en el grupo SENIAT
  de la pestaña Ajustes avanzados de los diarios de ventas.
- **Contactos y compañías**: tipo de contribuyente (ordinario, formal o
  especial), en sus formularios.

Las vistas solo filtran por país y tipo de documento. Las validaciones
fiscales, las reglas de visibilidad por medio de emisión y los reportes están
en `l10n_ve_seniat`, que depende de este módulo.
