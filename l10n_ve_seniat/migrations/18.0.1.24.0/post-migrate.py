from odoo.tools import SQL

_OBSOLETE_TABLES = (
    "res_company_l10n_ve_emission_medium_rel",
    "l10n_ve_emission_medium",
)


def migrate(cr, version):
    if not version:
        return
    for table in _OBSOLETE_TABLES:
        cr.execute(SQL("DROP TABLE IF EXISTS %s", SQL.identifier(table)))
