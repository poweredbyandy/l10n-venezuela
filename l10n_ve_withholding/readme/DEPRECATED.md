# DEPRECATED — `type.person` / `type_person_id`

> Estado: **deprecado desde 18.0.1.8.0** (l10n_ve_withholding) y
> 18.0.1.26.0 (l10n_ve_seniat). Eliminación planificada para el próximo
> major (Odoo 19/20). No usar en código nuevo.

`type_person_id` mezclaba la naturaleza del titular, su situación
territorial y las excepciones del tarifario ISLR en una sola clave manual.
Fue reemplazado por dos ejes limpios y una categoría.

## Reemplazos

| Campo deprecado | Reemplazo |
|---|---|
| `res.partner.type_person_id` | `res.partner.l10n_ve_person_type` (computado) + `res.partner.l10n_ve_islr_category` |
| `res.partner.type_person_id` (territorio) | `res.partner.l10n_ve_tax_residence` |
| `payment.concept.line.type_person_id` | `payment.concept.line.l10n_ve_person_type` + `payment.concept.line.l10n_ve_islr_category` |
| `res.company.type_person_id` / settings | `l10n_ve_person_type` (relacionado, readonly) + `l10n_ve_islr_category` |
| `type.person` `_get_default_type_person_id()` | sin reemplazo: el default automático dejó de existir |

## Mapeo de respaldo (usado por la migración y el matcher legacy)

| `type.person` (xml_id corto) | `l10n_ve_person_type` | `l10n_ve_islr_category` |
|---|---|---|
| `type_person_l10n_ve_withholding` (PN Residente) | `pn_resident` | `standard` |
| `type_person_two_l10n_ve_withholding` (PN No Residente) | `pn_non_resident` | `standard` |
| `type_person_three_l10n_ve_withholding` (PJ Domiciliada) | `pj_domiciled` | `standard` |
| `type_person_four_l10n_ve_withholding` (PJ No Domiciliada) | `pj_non_domiciled` | `standard` |
| `type_person_five_l10n_ve_withholding` (Instituciones Financieras No Dom.) | `pj_non_domiciled` | `financial_institution` |
| `type_person_six_l10n_ve_withholding` (Otras PJ No Domiciliada) | `pj_non_domiciled` | `other` |
| `type_person_seven_l10n_ve_withholding` (PJ Emisora de Radio Dom.) | `pj_domiciled` | `radio_broadcaster` |

El mapeo canónico vive en
`l10n_ve_withholding/models/type_person.py::TYPE_PERSON_MAP`.

## Qué queda en la base de datos y por qué

- Las columnas `type_person_id` (partner, línea de concepto, compañía) y la
  tabla `type.person` **no se borran** en 18.0: quedan congeladas como
  respaldo histórico — `readonly=True`, sin default, invisibles en las
  vistas y sin que ningún código las vuelva a escribir.
- El matcher de conceptos usa `(l10n_ve_person_type, l10n_ve_islr_category)`.
  Solo como **fallback** (con warning en el log) usa `type_person_id` cuando
  una línea de concepto no se pudo migrar (p. ej. una fila `type.person`
  custom del cliente que no mapea a los ejes nuevos).
- La migración 18.0.1.8.0 respalda además todas las líneas de retención en
  `l10n_ve_retention_line_bak_18_0_1_8_0` antes de cambiar la clasificación
  (ver `docs/adr/0002`).

## Criterio para eliminar en el próximo major

1. Confirmar con los clientes que no queda ninguna línea de concepto con
   `l10n_ve_person_type IS NULL` (el log del post-migrate 18.0.1.8.0 lo
   reporta).
2. Borrar el fallback legacy del matcher
   (`_l10n_ve_get_payment_concept_line`), la columna `type_person_id`, la
   tabla `type.person`, su menú/vistas y el modelo en sí.
3. Borrar las tablas de respaldo de migración una vez auditadas.
