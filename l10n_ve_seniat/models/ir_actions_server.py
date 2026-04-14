# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models

L10N_VE_SKIP_UNBIND = "l10n_ve_skip_server_action_unbind"


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get(L10N_VE_SKIP_UNBIND):
            records._l10n_ve_unbind_account_move_bindings()
        return records

    def write(self, vals):
        res = super().write(vals)
        if not self.env.context.get(L10N_VE_SKIP_UNBIND):
            self._l10n_ve_unbind_account_move_bindings()
        return res

    def _l10n_ve_unbind_account_move_bindings(self):
        move_model = self.env["ir.model"]._get("account.move")
        if not move_model:
            return
        to_clear = self.sudo().filtered(lambda a: a.binding_model_id == move_model)
        if to_clear:
            to_clear.with_context(**{L10N_VE_SKIP_UNBIND: True}).write(
                {"binding_model_id": False}
            )

    @api.model
    def _l10n_ve_unbind_all_account_move_bindings(self):
        move_model = self.env["ir.model"]._get("account.move")
        if not move_model:
            return
        self.sudo().search([("binding_model_id", "=", move_model.id)])._l10n_ve_unbind_account_move_bindings()
