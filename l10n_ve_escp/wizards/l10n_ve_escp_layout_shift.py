from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nVeEscpLayoutShift(models.TransientModel):
    _name = "l10n.ve.escp.layout.shift"
    _description = "Mover diseño ESC/P verticalmente"

    report_id = fields.Many2one(
        "l10n.ve.escp.report",
        string="Reporte",
        required=True,
        ondelete="cascade",
    )
    lines = fields.Integer(
        string="Líneas",
        default=2,
        required=True,
        help="Cantidad de líneas a subir o bajar.",
    )
    direction = fields.Selection(
        [("up", "Subir"), ("down", "Bajar")],
        string="Dirección",
        required=True,
        default="up",
    )
    include_margin = fields.Boolean(
        string="Incluir margen superior",
        help="También mueve el margen superior del reporte.",
    )

    def action_apply(self):
        self.ensure_one()
        if self.lines < 1:
            raise UserError(_("Indique al menos una línea."))
        delta = -self.lines if self.direction == "up" else self.lines
        self.report_id.shift_layout_rows(delta, self.include_margin)
        return {"type": "ir.actions.act_window_close"}
