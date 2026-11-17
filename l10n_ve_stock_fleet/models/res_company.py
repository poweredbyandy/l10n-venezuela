from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_own_fleet = fields.Boolean(
        string="Flota propia",
        help=(
            "Si está activo, el transportista y el vehículo se toman de la flota. "
            "El nombre y la matrícula quedan guardados en el albarán."
        ),
    )
