# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class L10nVeBookFolioVoid(models.Model):
    _name = "l10n_ve.book.folio.void"
    _description = "Motivo de anulación de folio (talonario sin movimiento)"
    _order = "id desc"

    reason = fields.Text(required=True)
    book_id = fields.Many2one(
        "account.book",
        string="Talonario",
        required=True,
        ondelete="cascade",
        index=True,
    )
    section_id = fields.Many2one(
        "account.book.section",
        string="Tramo",
        required=True,
        ondelete="restrict",
        index=True,
    )
    company_id = fields.Many2one(
        related="book_id.company_id",
        store=True,
        readonly=True,
    )

    def name_get(self):
        res = []
        for rec in self:
            text = (rec.reason or "").strip().replace("\n", " ")
            if len(text) > 80:
                text = text[:77] + "…"
            res.append((rec.id, text or str(rec.id)))
        return res
