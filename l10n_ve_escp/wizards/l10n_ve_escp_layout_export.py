import base64
import json

from odoo import fields, models


class L10nVeEscpLayoutExport(models.TransientModel):
    _name = "l10n.ve.escp.layout.export"
    _description = "Exportar diseño ESC/P"

    report_id = fields.Many2one(
        "l10n.ve.escp.report",
        string="Reporte",
        required=True,
        ondelete="cascade",
    )

    def action_export(self):
        self.ensure_one()
        payload = json.dumps(
            self.report_id.export_layout_data(), ensure_ascii=False, indent=2
        ).encode("utf-8")
        attachment = self.env["ir.attachment"].create(
            {
                "name": self.report_id._layout_filename(self.report_id.name),
                "type": "binary",
                "raw": payload,
                "mimetype": "application/json",
            }
        )
        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % attachment.id,
            "target": "self",
        }
