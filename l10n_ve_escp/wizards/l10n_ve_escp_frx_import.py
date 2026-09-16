import base64

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..models.l10n_ve_escp_report import CPI_SELECTION, LPI_SELECTION
from ..report.escp_engine import CPI_CHARS_PER_INCH
from ..report.frx_parser import OBJ_FIELD, OBJ_LABEL, OBJ_LINE, frx_layout, parse_frx

FONT_BOLD = 1
WIDE_FONT_SIZE = 12


class L10nVeEscpFrxImport(models.TransientModel):
    _name = "l10n.ve.escp.frx.import"
    _description = "Importar reporte Visual FoxPro (FRX)"

    name = fields.Char(string="Nombre del reporte", required=True)
    model_id = fields.Many2one(
        "ir.model",
        string="Modelo",
        required=True,
        domain=[("transient", "=", False)],
        ondelete="cascade",
    )
    frx_file = fields.Binary(string="Archivo .frx", required=True)
    frx_filename = fields.Char()
    frt_file = fields.Binary(string="Archivo .frt (memos)")
    frt_filename = fields.Char()
    cpi = fields.Selection(CPI_SELECTION, default="17", required=True)
    lpi = fields.Selection(LPI_SELECTION, default="6", required=True)
    paper_height_in = fields.Float(default=11.0, digits=(6, 2))
    detail_expr = fields.Char(
        string="Registros del detalle",
        help="Expresión para la banda de detalle, p. ej. o.invoice_line_ids.",
    )
    import_lines = fields.Boolean(
        string="Importar líneas horizontales",
        help="Convierte las líneas del diseño en rellenos de guiones. Desactívelo "
        "para formularios preimpresos.",
    )

    def _expression_map(self):
        model = self.env[self.model_id.model]
        if hasattr(model, "_l10n_ve_escp_frx_expression_map"):
            return model._l10n_ve_escp_frx_expression_map()
        return {}

    @staticmethod
    def _string_literal(expr):
        expr = (expr or "").strip()
        if len(expr) < 2 or expr[0] not in "\"'" or expr[-1] != expr[0]:
            return None
        inner = expr[1:-1]
        if expr[0] in inner:
            return None
        return inner.replace("\r\n", "\n").replace("\r", "\n")

    def _object_vals(self, item, cpi_chars, lpi, expression_map):
        objtype = int(item.get("OBJTYPE", 0))
        row = int(round(item["rel_vpos"] * lpi / 10000.0))
        col = int(round(float(item.get("HPOS") or 0.0) * cpi_chars / 10000.0))
        width = max(1, int(round(float(item.get("WIDTH") or 0.0) * cpi_chars / 10000.0)))
        height = max(1, int(round(float(item.get("HEIGHT") or 0.0) * lpi / 10000.0)))
        font_style = int(item.get("FONTSTYLE") or 0)
        font_size = float(item.get("FONTSIZE") or 0.0)
        bold = bool(font_style & FONT_BOLD)
        wide = font_size >= WIDE_FONT_SIZE
        style = (
            "bold_wide" if bold and wide else "wide" if wide else "bold" if bold else "normal"
        )
        picture = item.get("PICTURE") or ""
        numeric = "9" in picture
        vals = {
            "row": row,
            "col": col,
            "width": width,
            "height": height,
            "style": style,
            "align": "right" if numeric else "left",
            "wrap": height > 1,
        }
        if objtype == OBJ_LINE:
            if float(item.get("WIDTH") or 0.0) < float(item.get("HEIGHT") or 0.0):
                return None
            vals.update({"kind": "hline", "height": 1, "style": "normal"})
            return vals
        expr = (item.get("EXPR") or "").strip()
        literal = self._string_literal(expr)
        if objtype == OBJ_LABEL or (objtype == OBJ_FIELD and literal is not None):
            text = literal if literal is not None else expr
            longest = max((len(part) for part in text.split("\n")), default=0)
            vals.update({"kind": "label", "text": text, "width": max(width, longest)})
            return vals
        mapped = expression_map.get(expr)
        vals.update(
            {
                "kind": "field",
                "foxpro_expr": expr[:255],
                "expr": mapped if mapped else repr(expr[:60]),
                "format": "text",
            }
        )
        return vals

    def action_import(self):
        self.ensure_one()
        frx = base64.b64decode(self.frx_file or b"")
        frt = base64.b64decode(self.frt_file or b"") if self.frt_file else b""
        try:
            records = parse_frx(frx, frt)
        except Exception as err:
            raise UserError(_("No se pudo leer el archivo FRX: %s", err)) from err
        page_width_fru, bands = frx_layout(records)
        if not bands:
            raise UserError(_("El archivo FRX no contiene bandas."))
        cpi_chars = CPI_CHARS_PER_INCH.get(self.cpi, 17.14)
        lpi = float(self.lpi)
        expression_map = self._expression_map()
        band_commands = []
        for band in bands:
            objects = []
            for item in band["objects"]:
                vals = self._object_vals(item, cpi_chars, lpi, expression_map)
                if vals is None:
                    continue
                if vals["kind"] == "hline" and not self.import_lines:
                    continue
                objects.append(fields.Command.create(vals))
            height = max(1, int(round(band["height_fru"] * lpi / 10000.0)))
            band_vals = {
                "band_type": band["type"],
                "height": height,
                "object_ids": objects,
            }
            if band["type"] == "detail":
                band_vals["detail_expr"] = self.detail_expr or ""
            band_commands.append(fields.Command.create(band_vals))
        report = self.env["l10n.ve.escp.report"].create(
            {
                "name": self.name,
                "model_id": self.model_id.id,
                "cpi": self.cpi,
                "lpi": self.lpi,
                "paper_width_in": round(page_width_fru / 10000.0, 2),
                "paper_height_in": self.paper_height_in,
                "band_ids": band_commands,
                "note": _(
                    "Importado de %s. Las expresiones FoxPro sin equivalencia se "
                    "muestran entre comillas; edítelas en cada objeto."
                )
                % (self.frx_filename or "FRX"),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "l10n.ve.escp.report",
            "res_id": report.id,
            "view_mode": "form",
            "target": "current",
        }
