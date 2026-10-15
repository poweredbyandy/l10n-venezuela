from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_ve_edi_tfhka_foreign_id_type = fields.Char(
        string="Tipo de identificación extranjera (TFHKA)",
        size=3,
        help=(
            "Código del documento de identidad de un comprador no domiciliado "
            "fuera de Venezuela (por ejemplo RUT, NIT o PAS). Se envía en "
            "tipoIdentificacion del comprador; el número se toma del NIF."
        ),
    )
