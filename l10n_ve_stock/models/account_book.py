# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models


class AccountBookDocument(models.Model):
    _inherit = "account.book.document"

    @api.model
    def _selection_document_ref(self):
        return super()._selection_document_ref() + [
            ("stock.picking", "Dispatch guide (picking)"),
        ]
