from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_dispatch_guide_section_id = fields.Many2one(
        "account.book.section",
        string="Tramo talonario (guía de despacho)",
        help=(
            "Tramo del talonario SENIAT para el N° de control de guías de despacho "
            "en albaranes de venta validados sin factura vinculada."
        ),
    )
