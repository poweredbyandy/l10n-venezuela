import base64

from odoo import _, models
from odoo.exceptions import UserError

DISPATCH_GUIDE_REPORT = "l10n_ve_stock.report_dispatch_guide"


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _l10n_ve_is_dispatch_guide_report(self, report):
        return (report.report_name or "") == DISPATCH_GUIDE_REPORT

    def _l10n_ve_check_block_dispatch_pdf_before_digital_sent(
        self, report_ref, res_ids, data=None
    ):
        if not res_ids:
            return
        report = self._get_report(report_ref)
        if not self._l10n_ve_is_dispatch_guide_report(report):
            return
        for picking in self.env["stock.picking"].browse(res_ids):
            if picking._l10n_ve_edi_dispatch_guide_blocking_print_before_digital_sent():
                raise UserError(
                    _(
                        "No puede imprimir la guia hasta que el envio a "
                        "facturacion digital finalice correctamente "
                        "(estado EDI: enviado)."
                    )
                )

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        self._l10n_ve_check_block_dispatch_pdf_before_digital_sent(
            report_ref, res_ids, data
        )
        report = self._get_report(report_ref)
        if report.model == "stock.picking" and res_ids and len(res_ids) == 1:
            picking = self.env["stock.picking"].browse(res_ids[0])
            if picking._l10n_ve_edi_tfhka_replace_dispatch_report_with_digital_pdf():
                if not picking._l10n_ve_edi_tfhka_ensure_dispatch_pdf_report():
                    raise UserError(
                        _(
                            "No hay PDF de facturacion digital para imprimir. "
                            "Verifique credenciales TFHKA en Ajustes y que la "
                            "emision en TFHKA haya generado el documento."
                        )
                    )
                attachment = picking.l10n_ve_edi_tfhka_pdf_attachment_id
                if attachment and attachment.datas:
                    return base64.b64decode(attachment.datas), "pdf"
                raise UserError(
                    _("El adjunto PDF de facturacion digital no esta disponible.")
                )
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)
