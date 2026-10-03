La localización venezolana mostraba en el login y en el backend la
versión instalada de `l10n_ve_seniat`. Esa etiqueta no describe el
release de Odoo y no pertenece al flujo fiscal del SENIAT.

Este módulo deja la etiqueta en un addon aparte y muestra la versión
de Odoo. Es opcional: `l10n_ve_seniat` no depende de él. Las bases que
ya usaban la localización lo reciben instalado al actualizar
`l10n_ve_seniat`.
