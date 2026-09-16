from odoo import fields, models


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    report_type = fields.Selection(
        selection_add=[("escp", "ESC/P (impresora matriz)")],
        ondelete={"escp": "cascade"},
    )
    l10n_ve_escp_report_id = fields.Many2one(
        "l10n.ve.escp.report", string="Reporte ESC/P", ondelete="cascade"
    )

    def _get_readable_fields(self):
        return super()._get_readable_fields() | {"l10n_ve_escp_report_id"}

    def report_action(self, docids, data=None, config=True):
        if self.report_type == "escp":
            action = super().report_action(docids, data=data, config=False)
            action["l10n_ve_escp_report_id"] = self.l10n_ve_escp_report_id.id
            return action
        return super().report_action(docids, data=data, config=config)

    def _render_escp(self, report_ref, res_ids, data=None):
        report = self._get_report(report_ref)
        records = self.env[report.model].browse(res_ids)
        escp_report = report.l10n_ve_escp_report_id
        escp_report._check_records(records)
        return escp_report._render_escp(records), "escp"
