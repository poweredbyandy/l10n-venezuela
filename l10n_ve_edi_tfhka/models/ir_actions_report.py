import base64

from odoo import _, models
from odoo.exceptions import UserError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        self._l10n_ve_check_block_invoice_pdf_before_digital_sent(
            report_ref, res_ids, data
        )
        report = self._get_report(report_ref)
        if report.model == "account.move" and res_ids and len(res_ids) == 1:
            move = self.env["account.move"].browse(res_ids[0])
            if move._l10n_ve_edi_tfhka_replace_invoice_report_with_digital_pdf():
                if not move._l10n_ve_edi_tfhka_ensure_invoice_pdf_report():
                    raise UserError(
                        _(
                            "No hay PDF de facturacion digital para imprimir. "
                            "Verifique credenciales TFHKA en Ajustes y que la emision en TFHKA haya generado el documento."
                        )
                    )
                att = move.invoice_pdf_report_id
                if att and att.datas:
                    return base64.b64decode(att.datas), "pdf"
                raise UserError(
                    _(
                        "El adjunto PDF de facturacion digital no esta disponible."
                    )
                )
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
