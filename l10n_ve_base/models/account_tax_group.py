from odoo import fields, models

ALIQUOT_TYPE_SELECTION = [
    ("exempt", "E - Exento"),
    ("general", "G - General"),
    ("reduced", "R - Reducido"),
    ("extend", "A - Extendida"),
]


class AccountTaxGroup(models.Model):
    _inherit = "account.tax.group"

    l10n_ve_aliquot_type = fields.Selection(
        selection=ALIQUOT_TYPE_SELECTION,
        string="Alícuota SENIAT",
    )
