# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import io

from odoo import fields, models

try:
    import xlsxwriter
except ImportError:  # pragma: no cover
    xlsxwriter = None


class L10nVePayrollDeclarationExport(models.TransientModel):
    _name = "l10n_ve.payroll.declaration.export"
    _description = "Venezuelan Payroll Declaration Export"

    declaration_type = fields.Selection(
        [
            ("faov", "FAOV"),
            ("inces", "INCES"),
            ("ivss", "IVSS / TIUNA"),
            ("cepp", "CEPP Forma 19"),
            ("islr", "ISLR Laboral"),
            ("mintra", "MINTRA"),
            ("rnet", "RNET"),
            ("he", "Overtime HE"),
        ],
        required=True,
        default="faov",
    )
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    file_data = fields.Binary(readonly=True)
    file_name = fields.Char(readonly=True)

    def action_export(self):
        self.ensure_one()
        output = io.BytesIO()
        if xlsxwriter:
            workbook = xlsxwriter.Workbook(output, {"in_memory": True})
            sheet = workbook.add_worksheet(self.declaration_type.upper())
            sheet.write(0, 0, "Declaration")
            sheet.write(0, 1, self.declaration_type)
            sheet.write(1, 0, "From")
            sheet.write(1, 1, str(self.date_from))
            sheet.write(2, 0, "To")
            sheet.write(2, 1, str(self.date_to))
            workbook.close()
            content = output.getvalue()
            ext = "xlsx"
        else:
            content = (
                f"{self.declaration_type};{self.date_from};{self.date_to}\n"
            ).encode()
            ext = "csv"
        self.write(
            {
                "file_data": base64.b64encode(content),
                "file_name": f"{self.declaration_type}_{self.date_from}_{self.date_to}.{ext}",
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }
