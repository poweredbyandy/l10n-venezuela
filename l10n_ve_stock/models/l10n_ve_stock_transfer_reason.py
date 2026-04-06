from odoo import fields, models


class L10nVeStockTransferReason(models.Model):
    _name = "l10n_ve.stock.transfer.reason"
    _description = "Motivo de traslado (Venezuela)"
    _order = "name"

    name = fields.Char(required=True, translate=True)
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        default=lambda self: self.env.company,
        index=True,
    )
