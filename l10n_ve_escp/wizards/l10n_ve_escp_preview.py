import base64
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..report.escp_engine import pages_to_html, pages_to_pdf


class L10nVeEscpPreview(models.TransientModel):
    _name = "l10n.ve.escp.preview"
    _description = "Vista previa de reporte ESC/P"

    report_id = fields.Many2one(
        "l10n.ve.escp.report", string="Reporte", required=True, readonly=True
    )
    res_model = fields.Char(readonly=True)
    res_ids = fields.Char(readonly=True)
    test_mode = fields.Boolean(
        string="Prueba",
        help="No ejecuta las validaciones ni las acciones posteriores a la impresión.",
    )
    record_count = fields.Integer(compute="_compute_preview")
    preview_html = fields.Html(
        string="Vista previa", compute="_compute_preview", sanitize=False
    )
    preview_pdf = fields.Text(string="Vista previa PDF", compute="_compute_preview")

    def _records(self):
        self.ensure_one()
        ids = json.loads(self.res_ids or "[]")
        model = self.res_model or self.report_id.model
        return self.env[model].browse([int(i) for i in ids]).exists()

    @api.depends("report_id", "res_model", "res_ids")
    def _compute_preview(self):
        for wizard in self:
            records = wizard._records() if wizard.report_id else None
            if not records:
                wizard.record_count = 0
                wizard.preview_html = False
                wizard.preview_pdf = False
                continue
            pages = []
            for record in records:
                pages.extend(wizard.report_id._render_pages(record))
            spec = wizard.report_id._spec()
            wizard.record_count = len(records)
            wizard.preview_html = pages_to_html(pages)
            pdf = pages_to_pdf(pages, spec)
            wizard.preview_pdf = base64.b64encode(pdf).decode("ascii") if pdf else False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        if not res.get("report_id") and ctx.get("default_report_action_name"):
            action = (
                self.env["ir.actions.report"]
                .sudo()
                .search([("report_name", "=", ctx["default_report_action_name"])], limit=1)
            )
            if action.l10n_ve_escp_report_id:
                res["report_id"] = action.l10n_ve_escp_report_id.id
        if res.get("report_id"):
            report = self.env["l10n.ve.escp.report"].browse(res["report_id"])
            res.setdefault("res_model", report.model)
            if not res.get("res_ids") and ctx.get("active_ids"):
                res["res_ids"] = json.dumps(ctx["active_ids"])
            records = self.env[res["res_model"]].browse(
                json.loads(res.get("res_ids") or "[]")
            )
            if not records:
                raise UserError(_("No hay registros que imprimir."))
            report._check_records(records, test_mode=res.get("test_mode"))
        return res

    def action_print(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "l10n_ve_escp_print",
            "name": _("Imprimir ESC/P (USB)"),
            "target": "new",
            "context": {"dialog_size": "small"},
            "params": {
                "report_id": self.report_id.id,
                "res_model": self.res_model or self.report_id.model,
                "res_ids": json.loads(self.res_ids or "[]"),
                "test_mode": self.test_mode,
            },
        }
