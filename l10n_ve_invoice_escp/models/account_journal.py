from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_escp_report_id = fields.Many2one(
        "l10n.ve.escp.report",
        string="Reporte ESC/P",
        domain="[('model', '=', 'account.move')]",
        help="Reporte ESC/P usado al imprimir facturas de este diario en papel "
        "continuo. Vacío usa el reporte de factura por defecto.",
    )
