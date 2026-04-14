# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nVeAccountMoveCancelWizard(models.TransientModel):
    _name = "l10n_ve.account.move.cancel.wizard"
    _description = "Anular documento con motivo (Venezuela)"

    move_id = fields.Many2one(
        "account.move",
        required=True,
        ondelete="cascade",
    )
    reason_id = fields.Many2one(
        "l10n_ve.invoice.cancel.reason",
        string="Motivo de anulación",
        required=True,
    )

    def action_confirm(self):
        self.ensure_one()
        move = self.move_id
        ve_code = self.env.ref("base.ve").code
        if move.country_code != ve_code:
            raise UserError(_("Este asistente solo aplica a documentos de Venezuela."))
        move.write({"l10n_ve_cancel_reason_id": self.reason_id.id})
        move.button_cancel()
        return {"type": "ir.actions.act_window_close"}
