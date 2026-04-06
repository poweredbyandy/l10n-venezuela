from odoo import models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        report = self._get_report(report_ref)
        if report.report_name == "l10n_ve_stock.report_dispatch_guide":
            pickings = self.env["stock.picking"].browse(res_ids or [])
            pickings.l10n_ve_dispatch_guide_report_check()
        pdf, rep_type = super()._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )
        if report.report_name == "l10n_ve_stock.report_dispatch_guide":
            pickings = self.env["stock.picking"].browse(res_ids or [])
            to_mark = pickings.filtered(
                lambda p: p.company_id.account_fiscal_country_id.code == "VE"
                and not p.l10n_ve_dispatch_guide_original_printed
            )
            if to_mark:
                to_mark.sudo().write({"l10n_ve_dispatch_guide_original_printed": True})
        return pdf, rep_type
