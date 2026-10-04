La validación de RIF vivía dentro de `l10n_ve_seniat` con su propia
expresión regular, sin pasar por `base_vat`. Odoo ya trae en `base_vat`
una validación de RIF venezolano, pero es estricta: exige el dígito
verificador y rechaza cédulas usadas en la práctica.

Este módulo une las dos: extiende la validación de `base_vat` para que
siga aceptando los formatos que la localización aceptaba y respeta el
ajuste de la compañía. `l10n_ve_seniat` depende de él.
