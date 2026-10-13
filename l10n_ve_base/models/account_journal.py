from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_emission_medium = fields.Selection(
        selection=[
            ("free", "Forma libre (correlativo de talonario)"),
            ("contingency", "Contingencia"),
            ("fiscal_machine", "Máquina fiscal"),
            ("digital", "Facturación digital"),
        ],
        string="Medio de emisión",
        copy=False,
        help=(
            "Forma libre: asigna correlativo desde el talonario interno. "
            "Contingencia: no usa el talonario; el N° de control se indica en la "
            "factura antes de confirmar. Máquina fiscal y facturación digital: "
            "tampoco generan correlativo automático del talonario; el N° de control "
            "debe consignarse manualmente antes de confirmar."
        ),
    )
