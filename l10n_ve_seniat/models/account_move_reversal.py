# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    l10n_ve_fiscal_country_code = fields.Char(
        related="company_id.account_fiscal_country_id.code",
    )

    @api.model
    def _l10n_ve_moves_from_create_vals(self, vals):
        if not vals.get("move_ids"):
            return self.env["account.move"]
        ids = []
        for command in vals["move_ids"]:
            if command[0] == 6:
                ids.extend(command[2])
            elif command[0] == 4:
                ids.append(command[1])
        return self.env["account.move"].browse(ids) if ids else self.env["account.move"]

    @api.model_create_multi
    def create(self, vals_list):
        cleaned = []
        for vals in vals_list:
            vals = dict(vals)
            company = None
            if vals.get("company_id"):
                company = self.env["res.company"].browse(vals["company_id"])
            elif vals.get("move_ids"):
                moves = self._l10n_ve_moves_from_create_vals(vals)
                if moves:
                    company = moves[0].company_id
            if company and company.account_fiscal_country_id.code == "VE":
                moves = self._l10n_ve_moves_from_create_vals(vals)
                if moves:
                    journals = moves.journal_id.filtered(lambda j: j.active)
                    if journals:
                        vals["journal_id"] = journals[0].id
                vals["date"] = fields.Date.context_today(self)
            cleaned.append(vals)
        return super().create(cleaned)

    def write(self, vals):
        if self.env.context.get("l10n_ve_skip_reversal_wizard_lock"):
            return super().write(vals)
        if {"journal_id", "date"} & set(vals):
            for rec in self:
                if rec.company_id.account_fiscal_country_id.code == "VE":
                    raise UserError(
                        _(
                            "No puede modificar el diario ni la fecha de reversión "
                            "en notas de crédito para empresas con fiscalidad venezolana."
                        )
                    )
        return super().write(vals)
