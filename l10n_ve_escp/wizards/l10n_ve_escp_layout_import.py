import base64
import json

from odoo import _, fields, models
from odoo.exceptions import UserError


class L10nVeEscpLayoutImport(models.TransientModel):
    _name = "l10n.ve.escp.layout.import"
    _description = "Importar diseño ESC/P"

    mode = fields.Selection(
        [
            ("replace", "Reemplazar el diseño del reporte seleccionado"),
            ("new", "Crear un reporte nuevo"),
        ],
        string="Modo",
        required=True,
        default="replace",
    )
    report_id = fields.Many2one(
        "l10n.ve.escp.report",
        string="Reporte destino",
        ondelete="cascade",
    )
    name = fields.Char(string="Nombre del reporte nuevo")
    layout_file = fields.Binary(string="Archivo .escp.json", required=True)
    layout_filename = fields.Char()

    def action_import(self):
        self.ensure_one()
        if not self.layout_file:
            raise UserError(_("Seleccione un archivo de diseño."))
        try:
            raw = base64.b64decode(self.layout_file)
            data = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as err:
            raise UserError(_("No se pudo leer el archivo JSON: %s") % err) from err

        Report = self.env["l10n.ve.escp.report"]
        if self.mode == "replace":
            if not self.report_id:
                raise UserError(_("Indique el reporte que desea actualizar."))
            report = Report.import_layout_data(data, target_report=self.report_id)
        else:
            report = Report.import_layout_data(data, name=self.name)
        return {
            "type": "ir.actions.act_window",
            "name": report.name,
            "res_model": "l10n.ve.escp.report",
            "res_id": report.id,
            "view_mode": "form",
            "target": "current",
        }
