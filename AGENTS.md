# AGENTS.md — migración 18.0 → 19.0

Este repositorio se está migrando de **Odoo 18.0 a Odoo 19.0**.

## Regla principal

**Todo cambio de migración se documenta en `docs/migrations/18.0-to-19.0.md`**
(bitácora). Si no actualizas ese archivo, el cambio está incompleto.

## Flujo de trabajo

- Rama de trabajo: **`19.0-migration`** (nunca commits directos a `18.0`).
- Al terminar un bloque de trabajo: PR `19.0-migration` → `18.0`.

1. Lee `docs/migrations/18.0-to-19.0.md` (estado y hallazgos abiertos).
2. Lee/reproduce el error en el log del build de migración de runbot:
   `http://23.27.140.107/runbot/static/build/<dest-19-0>/logs/migrate_18_to_19.txt`
3. Haz el cambio mínimo para portar a 19.0 (código, vistas, datos,
   manifiestos). No cambies comportamiento de negocio.
4. Si hacen falta scripts de migración, van en `migrations/<version>/pre|post-*.py`
   del módulo (formato Odoo/OpenUpgrade).
5. Commit en `19.0-migration` con prefijo `mig(19.0): ...` (o `fix`/`feat` si
   aplica).
6. Actualiza la bitácora: qué error, qué se cambió, archivos y estado.
7. Push a `19.0-migration`: eso dispara el build 19.0 en runbot. Revisa el
   resultado y vuelve al paso 1 hasta que la migración pase.
8. Cuando pase, deja el PR `19.0-migration` → `18.0` listo para revisión.

## Reglas técnicas

- No `force push`, no reescribir historia, no tocar otras ramas ni tags.
- No modificar Odoo core ni dependencias OCA: si el fallo es de
  Odoo/OpenUpgrade, documéntalo como `aceptado` en la bitácora.
- El código debe seguir funcionando en 18.0 **y** 19.0. Usa
  `odoo.release.version_info` para las diferencias.
- Cambios típicos 18→19: `groups_id` → `group_ids`,
  `account.fiscal.position.tax.tax_src_id` eliminado, cambios en
  `<field name="states">`, etc. Verifica contra el código de Odoo 19.
- Ejecuta `checklog-odoo.cfg` (pre-commit) si está disponible.

## Skills

Están en `.agents/skills/odoo-skills/skills/` (igual que en el entorno local):
`odoo`, `odoo-19.0`, `odoo-migration`, `odoo-code-review`, etc.
