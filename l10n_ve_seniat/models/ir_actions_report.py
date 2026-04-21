from odoo import _, fields, models
from odoo.exceptions import UserError


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _l10n_ve_is_account_invoice_pdf_report(self, report):
        if report.model != "account.move":
            return False
        rname = (report.report_name or "")
        if "report_invoice" in rname:
            return True
        return "invoice" in rname.lower() and "payment" not in rname.lower()

    def _l10n_ve_is_ve_blockable_invoice_report(self, report_ref):
        report = self._get_report(report_ref)
        if hasattr(self, "_is_invoice_report") and self._is_invoice_report(report_ref):
            return True
        return self._l10n_ve_is_account_invoice_pdf_report(report)

    def _l10n_ve_check_block_invoice_pdf_before_digital_sent(self, report_ref, res_ids, data):
        data = data or {}
        if not res_ids:
            return
        if not self._l10n_ve_is_ve_blockable_invoice_report(report_ref):
            return
        for move in self.env["account.move"].browse(res_ids):
            if move._l10n_ve_block_invoice_pdf_contingency():
                raise UserError(
                    _(
                        "En contingencia no esta permitido imprimir ni descargar el PDF "
                        "de la factura (ni en borrador ni confirmada)."
                    )
                )
        if data.get("proforma"):
            return
        for move in self.env["account.move"].browse(res_ids):
            if move._l10n_ve_blocking_invoice_report_before_digital_sent():
                raise UserError(
                    _(
                        "No puede imprimir ni descargar la factura hasta que el envio a la "
                        "imprenta digital finalice correctamente (estado EDI: enviado)."
                    )
                )

    def _pre_render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        self._l10n_ve_check_block_invoice_pdf_before_digital_sent(report_ref, res_ids, data)
        return super()._pre_render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        pdf, report_type = super()._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )

        if self.env.context.get("l10n_ve_invoice"):
            moves = (
                self.env["account.move"]
                .browse(res_ids or [])
                .filtered(
                    lambda m: m.company_id.account_fiscal_country_id.code == "VE"
                    and m.move_type in ("out_invoice", "out_refund")
                    and m.state == "posted"
                )
            )
            to_mark = moves.filtered(lambda m: not m.l10n_ve_invoice_original_printed)
            for move in to_mark:
                write_vals = {"l10n_ve_invoice_original_printed": True}
                if (
                    move.l10n_ve_journal_emission_medium == "fiscal_machine"
                    and not move.l10n_ve_invoice_date
                ):
                    write_vals["l10n_ve_invoice_date"] = fields.Datetime.now()
                move.sudo().write(write_vals)

        return pdf, report_type
