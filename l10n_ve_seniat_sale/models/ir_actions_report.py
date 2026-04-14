from odoo import api, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    @api.model
    def _l10n_ve_unbind_extra_sale_order_pdf_reports(self):
        main = self.env.ref("sale.action_report_saleorder", raise_if_not_found=False)
        if not main:
            return
        extras = self.sudo().search(
            [
                ("model", "=", "sale.order"),
                ("report_type", "=", "qweb-pdf"),
                ("id", "!=", main.id),
            ]
        )
        extras.write({"binding_model_id": False})
