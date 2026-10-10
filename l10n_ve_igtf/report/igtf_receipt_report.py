from odoo import api, models


class ReportIgtfReceipt(models.AbstractModel):
    _name = "report.l10n_ve_igtf.report_igtf_receipt"
    _description = "IGTF Collection Receipt"

    @api.model
    def _get_report_values(self, docids, data=None):
        payments = self.env["account.payment"].browse(docids)
        return {
            "doc_ids": payments.ids,
            "doc_model": "account.payment",
            "docs": payments,
            "receipt_values": {
                payment.id: payment._l10n_ve_igtf_get_receipt_values()
                for payment in payments
            },
        }
