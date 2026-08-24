from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    l10n_ve_dispatch_guide_enabled = fields.Boolean(
        related="company_id.l10n_ve_dispatch_guide_enabled",
        readonly=True,
    )
    l10n_ve_dispatch_guide_section_id = fields.Many2one(
        "account.book.section",
        string="Tramo talonario (guía de despacho)",
        check_company=True,
        help=(
            "Tramo del talonario SENIAT para el N° de control de guías de despacho "
            "en albaranes de venta validados sin factura vinculada, para operaciones "
            "de este almacén."
        ),
    )
