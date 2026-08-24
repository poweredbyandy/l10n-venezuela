from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    display_type = fields.Selection(
        selection_add=[("l10n_ve_igtf", "IGTF")],
        ondelete={"l10n_ve_igtf": "set rounding"},
    )
