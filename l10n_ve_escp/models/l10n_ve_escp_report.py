import base64
import json
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date, format_datetime, formatLang
from odoo.tools.safe_eval import datetime as safe_datetime
from odoo.tools.safe_eval import safe_eval
from odoo.tools.safe_eval import time as safe_time

from ..report.escp_engine import (
    CPI_CHARS_PER_INCH,
    STYLE_FLAGS,
    Grid,
    pages_to_escp,
    pages_to_html,
    pages_to_pdf,
    wrap,
)

_logger = logging.getLogger(__name__)

CPI_SELECTION = [
    ("10", "10 CPI (Pica)"),
    ("12", "12 CPI (Elite)"),
    ("15", "15 CPI"),
    ("17", "17 CPI (Pica condensada)"),
    ("20", "20 CPI (Elite condensada)"),
]
LPI_SELECTION = [("6", "6 LPI (1/6 pulgada)"), ("8", "8 LPI (1/8 pulgada)")]
BAND_TYPES = [
    ("title", "Título (solo primera página)"),
    ("page_header", "Encabezado de página"),
    ("column_header", "Títulos de columnas"),
    ("detail", "Detalle"),
    ("summary", "Resumen (solo última página)"),
    ("page_footer", "Pie de página"),
]
BAND_ORDER = {key: index for index, (key, _label) in enumerate(BAND_TYPES)}
LAYOUT_VERSION = 1
LAYOUT_REPORT_FIELDS = (
    "name",
    "model",
    "cpi",
    "lpi",
    "paper_width_in",
    "paper_height_in",
    "margin_top_lines",
    "print_quality",
    "print_head_pins",
    "show_in_print_menu",
    "note",
)
STYLE_SELECTION = [
    ("normal", "Normal"),
    ("bold", "Negrita"),
    ("wide", "Ancho doble"),
    ("bold_wide", "Negrita y ancho doble"),
    ("underline", "Subrayado"),
    ("bold_underline", "Negrita y subrayado"),
    ("small", "Pequeña"),
    ("small_bold", "Pequeña negrita"),
    ("small_underline", "Pequeña subrayada"),
    ("small_bold_underline", "Pequeña negrita subrayada"),
]


class _Namespace(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as err:
            raise AttributeError(name) from err


class _EvalRecord:
    """Wraps a record for report expressions.

    Extras (shortcuts from business modules) take precedence; anything else
    is read from the underlying Odoo record, including related fields and
    recordset methods.
    """

    __slots__ = ("_extras", "_record")

    def __init__(self, record, extras=None):
        self._record = record
        self._extras = extras or {}

    def __getattr__(self, name):
        if name in self._extras:
            return self._extras[name]
        record = self._record
        if not record:
            if name.endswith("_id") or name == "id":
                return False
            return ""
        return getattr(record, name)

    def __bool__(self):
        return bool(self._record)


class L10nVeEscpReport(models.Model):
    _name = "l10n.ve.escp.report"
    _description = "Reporte ESC/P"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    model_id = fields.Many2one(
        "ir.model",
        string="Modelo",
        required=True,
        ondelete="cascade",
        domain=[("transient", "=", False)],
        default=lambda self: self._default_model_id(),
    )
    model = fields.Char(related="model_id.model", store=True)
    company_id = fields.Many2one("res.company")
    cpi = fields.Selection(
        CPI_SELECTION, string="Caracteres por pulgada", default="17", required=True
    )
    lpi = fields.Selection(
        LPI_SELECTION, string="Líneas por pulgada", default="6", required=True
    )
    paper_width_in = fields.Float(
        string="Ancho imprimible (pulgadas)", default=8.5, digits=(6, 2)
    )
    paper_height_in = fields.Float(
        string="Alto del formulario (pulgadas)",
        default=11.0,
        digits=(6, 2),
        help="Alto de cada hoja del papel continuo. Define la longitud de página "
        "(ESC C) y el alto de la vista previa.",
    )
    line_width = fields.Integer(
        string="Ancho de línea (caracteres)",
        compute="_compute_line_width",
        store=True,
        readonly=False,
    )
    page_rows = fields.Integer(
        string="Líneas por página", compute="_compute_page_rows"
    )
    margin_top_lines = fields.Integer(
        string="Margen superior (líneas)",
        default=0,
        help="Líneas en blanco antes de la primera banda.",
    )
    print_quality = fields.Selection(
        [
            ("draft", "Borrador (letra fina, un golpe)"),
            ("draft_double", "Borrador doble golpe (letra fina, más oscura)"),
            ("nlq", "Calidad carta NLQ (letra gruesa)"),
        ],
        string="Calidad de impresión",
        default="draft_double",
        required=True,
    )
    print_head_pins = fields.Selection(
        [("9", "9 agujas"), ("24", "24 agujas")],
        string="Agujas del cabezal",
        default="9",
        required=True,
        help="Solo afecta a la vista previa.",
    )
    band_ids = fields.One2many(
        "l10n.ve.escp.report.band", "report_id", string="Bandas", copy=True
    )
    report_action_id = fields.Many2one(
        "ir.actions.report", string="Acción de reporte", readonly=True, copy=False
    )
    show_in_print_menu = fields.Boolean(
        string="Mostrar en el menú Imprimir",
        default=True,
        help="Publica una acción de reporte ESC/P en el menú Imprimir del modelo.",
    )
    sample_ref = fields.Reference(
        selection="_selection_sample_ref",
        string="Registro de muestra",
        help="Registro usado por la vista previa.",
    )
    preview_html = fields.Html(
        string="Vista previa", compute="_compute_preview", sanitize=False
    )
    preview_pdf = fields.Text(string="Vista previa PDF", compute="_compute_preview")
    note = fields.Text(string="Notas")

    @api.model
    def _default_model_id(self):
        model_name = self.env.context.get("default_model_name")
        if not model_name:
            return False
        return self.env["ir.model"].sudo()._get(model_name)

    @api.model
    def _selection_sample_ref(self):
        return [
            (model.model, model.name)
            for model in self.env["ir.model"]
            .sudo()
            .search([("transient", "=", False)], order="name")
        ]

    @api.depends("cpi", "paper_width_in")
    def _compute_line_width(self):
        for report in self:
            chars = CPI_CHARS_PER_INCH.get(report.cpi, 17.14)
            width = int(chars * (report.paper_width_in or 0.0))
            report.line_width = max(40, min(255, width)) if width else 145

    @api.depends("lpi", "paper_height_in")
    def _compute_page_rows(self):
        for report in self:
            report.page_rows = int(
                round(float(report.lpi or 6) * (report.paper_height_in or 0.0))
            )

    @api.depends(
        "sample_ref",
        "cpi",
        "lpi",
        "line_width",
        "paper_width_in",
        "paper_height_in",
        "print_head_pins",
        "print_quality",
        "margin_top_lines",
        "band_ids",
        "band_ids.height",
        "band_ids.band_type",
        "band_ids.detail_expr",
        "band_ids.detail_rows",
        "band_ids.object_ids",
        "band_ids.object_ids.row",
        "band_ids.object_ids.col",
        "band_ids.object_ids.width",
        "band_ids.object_ids.height",
        "band_ids.object_ids.align",
        "band_ids.object_ids.style",
        "band_ids.object_ids.kind",
        "band_ids.object_ids.text",
        "band_ids.object_ids.expr",
        "band_ids.object_ids.format",
        "band_ids.object_ids.digits",
        "band_ids.object_ids.currency_expr",
        "band_ids.object_ids.wrap",
        "band_ids.object_ids.print_when",
        "band_ids.object_ids.fill_char",
        "band_ids.object_ids.active",
    )
    def _compute_preview(self):
        for report in self:
            record = report.sample_ref
            if not record or not report.model or record._name != report.model:
                report.preview_html = False
                report.preview_pdf = False
                continue
            try:
                pages = report._render_pages(record.exists())
            except Exception as err:
                _logger.debug("ESC/P preview failed", exc_info=True)
                report.preview_html = "<pre>%s</pre>" % _(
                    "No se pudo generar la vista previa: %s", err
                )
                report.preview_pdf = False
                continue
            report.preview_html = pages_to_html(pages)
            pdf = pages_to_pdf(pages, report._spec())
            report.preview_pdf = base64.b64encode(pdf).decode("ascii") if pdf else False

    @api.constrains("band_ids")
    def _check_bands(self):
        for report in self:
            details = report.band_ids.filtered(lambda b: b.band_type == "detail")
            if len(details) > 1:
                raise ValidationError(_("Un reporte solo puede tener una banda de detalle."))
            for band_type in ("title", "page_header", "column_header", "summary", "page_footer"):
                if len(report.band_ids.filtered(lambda b: b.band_type == band_type)) > 1:
                    raise ValidationError(
                        _("Solo puede haber una banda de tipo %s.", band_type)
                    )

    @api.model_create_multi
    def create(self, vals_list):
        reports = super().create(vals_list)
        reports._sync_report_action()
        return reports

    def write(self, vals):
        res = super().write(vals)
        if {"name", "model_id", "active", "show_in_print_menu", "company_id"} & set(vals):
            self._sync_report_action()
        return res

    def unlink(self):
        actions = self.report_action_id
        res = super().unlink()
        actions.sudo().unlink()
        return res

    def _sync_report_action(self):
        actions_model = self.env["ir.actions.report"].sudo()
        for report in self:
            vals = {
                "name": report.name,
                "model": report.model,
                "report_type": "escp",
                "report_name": f"l10n_ve_escp.report_{report.id}",
                "l10n_ve_escp_report_id": report.id,
                "binding_model_id": report.model_id.id
                if report.show_in_print_menu and report.active
                else False,
                "binding_type": "report",
            }
            if report.report_action_id:
                report.report_action_id.sudo().write(vals)
            else:
                report.report_action_id = actions_model.create(vals)

    def _spec(self):
        self.ensure_one()
        return {
            "cpi": self.cpi,
            "lpi": self.lpi,
            "line_width": self.line_width or 145,
            "paper_width_in": self.paper_width_in,
            "paper_height_in": self.paper_height_in,
            "quality": self.print_quality,
            "pins": int(self.print_head_pins or 9),
        }

    def _base_eval_context(self, record):
        env = self.env

        def money(amount, currency=None, digits=None):
            if currency is None or not currency:
                return formatLang(env, amount or 0.0, digits=digits if digits is not None else 2)
            return formatLang(env, amount or 0.0, currency_obj=currency)

        def num(amount, digits=2):
            return formatLang(env, amount or 0.0, digits=digits)

        def qty(amount):
            amount = amount or 0.0
            if amount == int(amount):
                return f"{amount:.0f}"
            return formatLang(env, amount, digits=2)

        def date(value, pattern=None):
            if not value:
                return ""
            if pattern:
                return fields.Date.to_date(value).strftime(pattern)
            return format_date(env, value)

        def datetime_(value, pattern=None, tz=True):
            if not value:
                return ""
            value = fields.Datetime.to_datetime(value)
            if tz:
                value = fields.Datetime.context_timestamp(record, value)
            if pattern:
                return value.strftime(pattern)
            return format_datetime(env, value)

        def words(amount, currency=None, lang=None):
            currency = currency or getattr(record, "currency_id", False)
            if not currency:
                return ""
            return currency.with_context(lang=lang or env.user.lang).amount_to_text(amount or 0.0)

        def wrap_(text, width):
            return wrap(text, width)

        def field(target, path, default=""):
            if not target or not path:
                return default
            parts = str(path).split(".")
            value = target
            for index, part in enumerate(parts):
                if value is None or value is False:
                    return default
                if isinstance(value, models.BaseModel):
                    if part not in value._fields:
                        return default
                    if index == len(parts) - 1 and len(value) != 1:
                        value = value.mapped(part)
                    else:
                        value = value[part]
                else:
                    value = getattr(value, part, default)
            if value is None or value is False:
                return default
            return value

        ctx = _Namespace(
            o=record,
            object=record,
            env=env,
            user=env.user,
            company=getattr(record, "company_id", False) or env.company,
            today=fields.Date.context_today(record),
            now=fields.Datetime.now(),
            datetime=safe_datetime,
            time=safe_time,
            money=money,
            num=num,
            qty=qty,
            date=date,
            datetime_fmt=datetime_,
            words=words,
            wrap=wrap_,
            field=field,
            upper=lambda value: (value or "").upper(),
            lower=lambda value: (value or "").lower(),
            strip=lambda value: (value or "").strip(),
            line=None,
            line_no=0,
            pl=_EvalRecord(None),
            page=1,
            page_count=1,
        )
        if hasattr(record, "_l10n_ve_escp_eval_context"):
            ctx.update(record._l10n_ve_escp_eval_context(self))
        return ctx

    def _line_eval_context(self, base_ctx, record, line, line_no):
        ctx = _Namespace(base_ctx)
        pl_extras = {}
        hook_data = {}
        if hasattr(record, "_l10n_ve_escp_line_eval_context"):
            hook_data = record._l10n_ve_escp_line_eval_context(self, line) or {}
            if isinstance(hook_data, dict):
                pl_value = hook_data.pop("pl", None)
                if pl_value is not None:
                    if isinstance(pl_value, (_Namespace, dict)):
                        pl_extras = dict(pl_value)
                    else:
                        pl_extras = {"value": pl_value}
                ctx.update(hook_data)
        ctx.update(
            {
                "line": line,
                "line_no": line_no,
                "pl": _EvalRecord(line, pl_extras),
            }
        )
        return ctx

    @staticmethod
    def _eval(expr, ctx):
        expr = (expr or "").strip()
        if not expr:
            return ""
        return safe_eval(expr, ctx, nocopy=True)

    def _detail_records(self, band, ctx):
        if not band or not band.detail_expr:
            return []
        value = self._eval(band.detail_expr, ctx)
        if value is None or value is False:
            return []
        if isinstance(value, models.BaseModel):
            return list(value)
        return list(value)

    def _band(self, band_type):
        return self.band_ids.filtered(lambda b: b.band_type == band_type)[:1]

    def _band_height(self, band_type):
        band = self._band(band_type)
        return band.height if band else 0

    def _layout_params(self, record=None):
        self.ensure_one()
        detail = self._band("detail")
        params = {
            "margin_top_lines": self.margin_top_lines,
            "detail_rows": detail.detail_rows if detail and detail.detail_rows else None,
        }
        if record and hasattr(record, "_l10n_ve_escp_layout_params"):
            override = record._l10n_ve_escp_layout_params(self) or {}
            if "margin_top_lines" in override:
                params["margin_top_lines"] = override["margin_top_lines"]
            if override.get("detail_rows") is not None:
                params["detail_rows"] = override["detail_rows"]
        return params

    def _layout_rows(self, record=None):
        self.ensure_one()
        params = self._layout_params(record)
        margin_top_lines = int(params.get("margin_top_lines") or 0)
        detail = self._band("detail")
        fixed = (
            margin_top_lines
            + self._band_height("title")
            + self._band_height("page_header")
            + self._band_height("column_header")
            + self._band_height("summary")
            + self._band_height("page_footer")
        )
        detail_height = max(1, detail.height) if detail else 1
        detail_rows = params.get("detail_rows")
        if detail_rows is None:
            page_rows = self.page_rows or (fixed + detail_height)
            detail_rows = max(1, (page_rows - fixed) // detail_height)
        else:
            detail_rows = max(1, int(detail_rows))
        return fixed, detail_rows, detail_height, margin_top_lines

    def _render_pages(self, record):
        self.ensure_one()
        record.ensure_one()
        base_ctx = self._base_eval_context(record)
        detail_band = self._band("detail")
        lines = self._detail_records(detail_band, base_ctx) if detail_band else []
        fixed, detail_rows, detail_height, margin_top_lines = self._layout_rows(record)
        base_ctx.update(
            {
                "detail_rows": detail_rows,
                "margin_top_lines": margin_top_lines,
            }
        )
        per_page = max(1, detail_rows)
        page_count = max(1, -(-len(lines) // per_page))
        pages = []
        for page_index in range(page_count):
            base_ctx.update({"page": page_index + 1, "page_count": page_count})
            page_lines = lines[page_index * per_page : (page_index + 1) * per_page]
            total_rows = fixed + per_page * detail_height
            if page_index:
                total_rows -= self._band_height("title")
            grid = Grid(total_rows, self.line_width or 145, escp_base_cpi=self.cpi)
            row = margin_top_lines
            if page_index == 0:
                row = self._place_band(grid, self._band("title"), row, base_ctx, record)
            row = self._place_band(grid, self._band("page_header"), row, base_ctx, record)
            row = self._place_band(grid, self._band("column_header"), row, base_ctx, record)
            if detail_band:
                for index, line in enumerate(page_lines):
                    line_ctx = self._line_eval_context(
                        base_ctx, record, line, page_index * per_page + index + 1
                    )
                    self._place_band(grid, detail_band, row, line_ctx, record)
                    row += detail_height
                row += (per_page - len(page_lines)) * detail_height
            else:
                row += per_page * detail_height
            if page_index == page_count - 1:
                row = self._place_band(grid, self._band("summary"), row, base_ctx, record)
            else:
                row += self._band_height("summary")
            self._place_band(grid, self._band("page_footer"), row, base_ctx, record)
            pages.append(grid)
        return pages

    def _place_band(self, grid, band, base_row, ctx, record):
        if not band:
            return base_row
        for obj in band.object_ids:
            if not obj.active:
                continue
            try:
                obj._place(grid, base_row, ctx)
            except Exception as err:
                _logger.warning("ESC/P object %s failed: %s", obj.display_name, err)
                grid.put(base_row + obj.row, obj.col, "#ERR", obj.width or 4)
        return base_row + band.height

    def _render_escp(self, records):
        self.ensure_one()
        pages = []
        for record in records:
            pages.extend(self._render_pages(record))
        return pages_to_escp(pages, self._spec())

    def _check_records(self, records, test_mode=False):
        self.ensure_one()
        records.check_access("read")
        if test_mode:
            return
        for record in records:
            if hasattr(record, "_l10n_ve_escp_check_print"):
                record._l10n_ve_escp_check_print(self)

    @api.model
    def _records_from_ids(self, report_id, res_model, res_ids):
        report = self.browse(int(report_id)).exists()
        if not report:
            raise UserError(_("El reporte ESC/P ya no existe."))
        if isinstance(res_ids, str):
            res_ids = json.loads(res_ids or "[]")
        if res_model and res_model != report.model:
            raise UserError(_("El reporte no corresponde al modelo %s.", res_model))
        return report, self.env[report.model].browse([int(i) for i in res_ids]).exists()

    @api.model
    def get_print_payload(self, report_id, res_model, res_ids, test_mode=False):
        report, records = self._records_from_ids(report_id, res_model, res_ids)
        report._check_records(records, test_mode=test_mode)
        raw = report._render_escp(records)
        return {"payload_b64": base64.b64encode(raw).decode("ascii")}

    @api.model
    def confirm_printed(self, report_id, res_model, res_ids):
        report, records = self._records_from_ids(report_id, res_model, res_ids)
        report._check_records(records)
        for record in records:
            if hasattr(record, "_l10n_ve_escp_after_print"):
                record._l10n_ve_escp_after_print(report)
        return True

    def _preview_action(self, records, test_mode=False):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Vista previa ESC/P"),
            "res_model": "l10n.ve.escp.preview",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_report_id": self.id,
                "default_res_model": records._name,
                "default_res_ids": json.dumps(records.ids),
                "default_test_mode": test_mode,
                "dialog_size": "extra-large",
            },
        }

    def action_preview_sample(self):
        self.ensure_one()
        if not self.sample_ref:
            raise UserError(_("Seleccione un registro de muestra."))
        return self._preview_action(self.sample_ref, test_mode=True)

    def action_open_designer(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "l10n_ve_escp_designer",
            "name": _("Diseñador: %s", self.name),
            "params": {"report_id": self.id},
        }

    @staticmethod
    def _layout_filename(name):
        slug = re.sub(r"[^\w\-]+", "_", name or "reporte", flags=re.UNICODE).strip("_")
        return "%s.escp.json" % (slug or "reporte")

    def export_layout_data(self):
        self.ensure_one()
        bands = []
        for band in self.band_ids.sorted(lambda b: (b.sequence, b.id)):
            objects = band.object_ids.with_context(active_test=False).sorted(
                lambda o: (o.row, o.col, o.id)
            )
            bands.append(
                {
                    **{name: band[name] for name in self.BAND_DESIGNER_FIELDS},
                    "objects": [
                        {
                            name: obj[name]
                            for name in self.OBJECT_DESIGNER_FIELDS
                            if name != "sequence"
                        }
                        for obj in objects
                    ],
                }
            )
        return {
            "format_version": LAYOUT_VERSION,
            "module": "l10n_ve_escp",
            "exported_at": fields.Datetime.to_string(fields.Datetime.now()),
            "report": {name: self[name] for name in LAYOUT_REPORT_FIELDS},
            "bands": bands,
        }

    def download_layout_export(self):
        self.ensure_one()
        payload = json.dumps(self.export_layout_data(), ensure_ascii=False, indent=2)
        return {
            "filename": self._layout_filename(self.name),
            "content": payload,
        }

    def action_export_layout(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Exportar diseño ESC/P"),
            "res_model": "l10n.ve.escp.layout.export",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {"default_report_id": self.id},
        }

    @api.model
    def import_layout_data(self, data, target_report=None, name=None):
        if not isinstance(data, dict):
            raise UserError(_("El archivo de diseño no es válido."))
        if data.get("format_version") != LAYOUT_VERSION:
            raise UserError(
                _("Versión de diseño no compatible (esperada %(expected)s, recibida %(got)s).")
                % {
                    "expected": LAYOUT_VERSION,
                    "got": data.get("format_version"),
                }
            )
        report_data = data.get("report") or {}
        model_name = report_data.get("model")
        if not model_name:
            raise UserError(_("El diseño no indica el modelo Odoo."))
        model = self.env["ir.model"].sudo().search([("model", "=", model_name)], limit=1)
        if not model:
            raise UserError(_("Modelo %(model)s no encontrado en esta base de datos.") % {"model": model_name})

        Report = self.env["l10n.ve.escp.report"]
        Band = self.env["l10n.ve.escp.report.band"]
        Obj = self.env["l10n.ve.escp.report.object"].with_context(active_test=False)

        if target_report:
            report = target_report
            if report.model != model_name:
                raise UserError(
                    _(
                        "El diseño es para %(src)s pero el reporte destino usa %(dst)s."
                    )
                    % {"src": model_name, "dst": report.model}
                )
            report.band_ids.unlink()
        else:
            vals = {
                name: report_data[name]
                for name in LAYOUT_REPORT_FIELDS
                if name in report_data and name not in ("name", "model")
            }
            vals.update(
                {
                    "name": name or report_data.get("name") or _("Reporte importado"),
                    "model_id": model.id,
                }
            )
            report = Report.create(vals)

        for band_data in data.get("bands") or []:
            band_vals = {
                name: band_data.get(name)
                for name in self.BAND_DESIGNER_FIELDS
                if name in band_data
            }
            band = Band.create({"report_id": report.id, **band_vals})
            for index, obj_data in enumerate(band_data.get("objects") or []):
                obj_vals = {
                    name: obj_data.get(name)
                    for name in self.OBJECT_DESIGNER_FIELDS
                    if name in obj_data and name != "foxpro_expr"
                }
                obj_vals["sequence"] = index * 10
                obj_vals["band_id"] = band.id
                Obj.create(obj_vals)
        return report

    def shift_layout_rows(self, delta, include_margin=False):
        self.ensure_one()
        if not delta:
            return
        Obj = self.env["l10n.ve.escp.report.object"].with_context(active_test=False)
        for obj in Obj.search([("report_id", "=", self.id)]):
            obj.row = max(0, obj.row + delta)
        if include_margin:
            self.margin_top_lines = max(0, self.margin_top_lines + delta)

    def action_open_layout_import(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Importar diseño ESC/P"),
            "res_model": "l10n.ve.escp.layout.import",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {
                "default_report_id": self.id,
                "default_mode": "replace",
            },
        }

    def action_open_layout_shift(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Mover diseño verticalmente"),
            "res_model": "l10n.ve.escp.layout.shift",
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {"default_report_id": self.id},
        }

    OBJECT_DESIGNER_FIELDS = (
        "kind",
        "row",
        "col",
        "width",
        "height",
        "align",
        "style",
        "text",
        "expr",
        "format",
        "digits",
        "currency_expr",
        "wrap",
        "print_when",
        "fill_char",
        "foxpro_expr",
        "active",
        "sequence",
    )
    BAND_DESIGNER_FIELDS = ("band_type", "height", "detail_expr", "detail_rows")

    def _designer_sample_values(self):
        self.ensure_one()
        values = {}
        record = self.sample_ref
        if not record or record._name != self.model or not record.exists():
            return values
        try:
            base_ctx = self._base_eval_context(record)
        except Exception as err:
            _logger.debug("designer sample context failed: %s", err)
            return values
        detail = self._band("detail")
        line_ctx = base_ctx
        if detail:
            try:
                lines = self._detail_records(detail, base_ctx)
            except Exception:
                lines = []
            if lines:
                line_ctx = self._line_eval_context(base_ctx, record, lines[0], 1)
        for band in self.band_ids:
            ctx = line_ctx if band.band_type == "detail" else base_ctx
            for obj in band.object_ids.with_context(active_test=False):
                try:
                    values[obj.id] = str(obj._value(ctx))
                except Exception as err:
                    values[obj.id] = "#ERR %s" % err
        return values

    def designer_load(self):
        self.ensure_one()
        sample = self.sample_ref if self.sample_ref and self.sample_ref._name == self.model else None
        fixed, detail_rows, detail_height, margin_top = self._layout_rows(sample)
        bands = []
        for band in self.band_ids.sorted(lambda b: (b.sequence, b.id)):
            objects = band.object_ids.with_context(active_test=False).sorted(
                lambda o: (o.sequence, o.id)
            )
            bands.append(
                {
                    "id": band.id,
                    **{name: band[name] for name in self.BAND_DESIGNER_FIELDS},
                    "objects": [
                        {"id": obj.id, **{name: obj[name] for name in self.OBJECT_DESIGNER_FIELDS}}
                        for obj in objects
                    ],
                }
            )
        return {
            "report": {
                "id": self.id,
                "name": self.name,
                "model": self.model,
                "line_width": self.line_width,
                "page_rows": self.page_rows,
                "margin_top_lines": margin_top,
                "detail_rows": detail_rows,
                "detail_height": detail_height,
                "sample": self.sample_ref.display_name if self.sample_ref else False,
            },
            "bands": bands,
            "sample_values": self._designer_sample_values(),
            "options": {
                "band_types": BAND_TYPES,
                "styles": STYLE_SELECTION,
                "kinds": self.env["l10n.ve.escp.report.object"]._fields["kind"].selection,
                "formats": self.env["l10n.ve.escp.report.object"]._fields["format"].selection,
                "aligns": self.env["l10n.ve.escp.report.object"]._fields["align"].selection,
            },
        }

    def designer_save(self, payload):
        self.ensure_one()
        self.check_access("write")
        Band = self.env["l10n.ve.escp.report.band"]
        Obj = self.env["l10n.ve.escp.report.object"].with_context(active_test=False)
        deleted_objects = [int(i) for i in payload.get("deleted_object_ids", []) if int(i) > 0]
        if deleted_objects:
            Obj.browse(deleted_objects).filtered(lambda o: o.report_id == self).unlink()
        deleted_bands = [int(i) for i in payload.get("deleted_band_ids", []) if int(i) > 0]
        if deleted_bands:
            Band.browse(deleted_bands).filtered(lambda b: b.report_id == self).unlink()
        for band_data in payload.get("bands", []):
            band_vals = {
                name: band_data.get(name)
                for name in self.BAND_DESIGNER_FIELDS
                if name in band_data
            }
            band_id = int(band_data.get("id") or 0)
            if band_id > 0:
                band = Band.browse(band_id)
                if band.report_id != self:
                    raise UserError(_("Banda inválida."))
                band.write(band_vals)
            else:
                band = Band.create({"report_id": self.id, **band_vals})
            for index, obj_data in enumerate(band_data.get("objects", [])):
                obj_vals = {
                    name: obj_data.get(name)
                    for name in self.OBJECT_DESIGNER_FIELDS
                    if name in obj_data and name != "foxpro_expr"
                }
                obj_vals["sequence"] = index * 10
                obj_vals["band_id"] = band.id
                obj_id = int(obj_data.get("id") or 0)
                if obj_id > 0:
                    obj = Obj.browse(obj_id)
                    if obj.report_id != self:
                        raise UserError(_("Objeto inválido."))
                    obj.write(obj_vals)
                else:
                    Obj.create(obj_vals)
        if "margin_top_lines" in payload:
            self.write({"margin_top_lines": int(payload["margin_top_lines"] or 0)})
        self.invalidate_recordset()
        return self.designer_load()

    def action_print_sample(self):
        self.ensure_one()
        if not self.sample_ref:
            raise UserError(_("Seleccione un registro de muestra."))
        return {
            "type": "ir.actions.client",
            "tag": "l10n_ve_escp_print",
            "name": _("Imprimir prueba"),
            "target": "new",
            "context": {"dialog_size": "small"},
            "params": {
                "report_id": self.id,
                "res_model": self.sample_ref._name,
                "res_ids": self.sample_ref.ids,
                "test_mode": True,
            },
        }


class L10nVeEscpReportBand(models.Model):
    _name = "l10n.ve.escp.report.band"
    _description = "Banda de reporte ESC/P"
    _order = "report_id, sequence, id"

    report_id = fields.Many2one(
        "l10n.ve.escp.report", required=True, ondelete="cascade"
    )
    sequence = fields.Integer(compute="_compute_sequence", store=True, readonly=False)
    name = fields.Char(compute="_compute_name")
    band_type = fields.Selection(BAND_TYPES, string="Tipo", required=True)
    height = fields.Integer(
        string="Alto (líneas)",
        default=1,
        required=True,
        help="Detalle: líneas por cada registro.",
    )
    detail_expr = fields.Char(
        string="Registros del detalle",
        help="Expresión Python que devuelve los registros a recorrer, p. ej. "
        "o.invoice_line_ids o [l for l in o.order_line if l.product_id].",
    )
    detail_rows = fields.Integer(
        string="Renglones por página",
        default=0,
        help="Cero: los que quepan en la hoja según el alto de las demás bandas.",
    )
    object_ids = fields.One2many(
        "l10n.ve.escp.report.object", "band_id", string="Objetos", copy=True
    )

    @api.depends("band_type")
    def _compute_sequence(self):
        for band in self:
            band.sequence = BAND_ORDER.get(band.band_type, 50) * 10

    @api.depends("band_type", "height")
    def _compute_name(self):
        labels = dict(BAND_TYPES)
        for band in self:
            band.name = "%s (%s)" % (labels.get(band.band_type, band.band_type), band.height)


class L10nVeEscpReportObject(models.Model):
    _name = "l10n.ve.escp.report.object"
    _description = "Objeto de reporte ESC/P"
    _order = "band_id, row, col, id"

    band_id = fields.Many2one(
        "l10n.ve.escp.report.band", required=True, ondelete="cascade"
    )
    report_id = fields.Many2one(related="band_id.report_id", store=True)
    band_type = fields.Selection(related="band_id.band_type", string="Banda")
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(compute="_compute_name")
    kind = fields.Selection(
        [("label", "Etiqueta"), ("field", "Campo"), ("hline", "Línea horizontal")],
        string="Tipo",
        default="field",
        required=True,
    )
    row = fields.Integer(string="Fila", help="Relativa al inicio de la banda.")
    col = fields.Integer(string="Columna")
    width = fields.Integer(string="Ancho", default=10)
    height = fields.Integer(
        string="Líneas", default=1, help="Líneas que puede ocupar el texto."
    )
    align = fields.Selection(
        [("left", "Izquierda"), ("center", "Centro"), ("right", "Derecha")],
        default="left",
        required=True,
    )
    style = fields.Selection(STYLE_SELECTION, default="normal", required=True)
    text = fields.Text(
        string="Texto",
        help="Etiqueta: texto fijo. Admite saltos de línea.",
    )
    expr = fields.Text(
        string="Expresión",
        help="Python evaluado con o (registro), line (registro del detalle), "
        "page, page_count y las funciones money(), num(), qty(), date(), "
        "datetime_fmt(), words(), upper().",
    )
    format = fields.Selection(
        [
            ("text", "Texto"),
            ("monetary", "Monetario"),
            ("float", "Decimal"),
            ("integer", "Entero"),
            ("date", "Fecha"),
            ("datetime", "Fecha y hora"),
        ],
        default="text",
        required=True,
    )
    digits = fields.Integer(string="Decimales", default=2)
    currency_expr = fields.Char(
        string="Moneda",
        help="Expresión de la moneda para el formato monetario. Vacío: o.currency_id.",
    )
    wrap = fields.Boolean(
        string="Ajustar texto",
        help="Reparte el texto en varias líneas dentro del ancho.",
    )
    print_when = fields.Char(
        string="Imprimir si",
        help="Condición Python; vacío imprime siempre.",
    )
    fill_char = fields.Char(string="Carácter de relleno", default="-", size=1)
    foxpro_expr = fields.Char(string="Expresión FoxPro", readonly=True)

    @api.depends("kind", "text", "expr")
    def _compute_name(self):
        for obj in self:
            if obj.kind == "label":
                obj.name = (obj.text or "").split("\n")[0][:40]
            elif obj.kind == "hline":
                obj.name = "─" * 6
            else:
                obj.name = (obj.expr or "")[:40]

    def _style_flags(self):
        return STYLE_FLAGS.get(self.style or "normal", 0)

    def _format_value(self, value, ctx):
        if value is None or value is False:
            return ""
        fmt = self.format
        if fmt == "monetary":
            currency = None
            if self.currency_expr:
                currency = self.report_id._eval(self.currency_expr, ctx)
            elif ctx.get("line") is not None and hasattr(ctx["line"], "currency_id"):
                currency = ctx["line"].currency_id
            else:
                currency = getattr(ctx.get("o"), "currency_id", None)
            return ctx["money"](value, currency)
        if fmt == "float":
            return ctx["num"](value, self.digits)
        if fmt == "integer":
            return f"{int(round(value or 0))}"
        if fmt == "date":
            return ctx["date"](value)
        if fmt == "datetime":
            return ctx["datetime_fmt"](value)
        if isinstance(value, models.BaseModel):
            return ", ".join(value.mapped("display_name"))
        if isinstance(value, (list, tuple)):
            return " ".join(str(v) for v in value)
        return str(value)

    def _value(self, ctx):
        self.ensure_one()
        if self.kind == "label":
            return self.text or ""
        if self.kind == "hline":
            return (self.fill_char or "-")[0] * max(1, self.width)
        return self._format_value(self.report_id._eval(self.expr, ctx), ctx)

    def _place(self, grid, base_row, ctx):
        self.ensure_one()
        if self.print_when and not self.report_id._eval(self.print_when, ctx):
            return
        text = self._value(ctx)
        style = self._style_flags()
        row = base_row + self.row
        width = self.width or (grid.width - self.col)
        if self.wrap:
            lines = wrap(text, grid.capacity(width, style))
        else:
            lines = [line.strip() for line in str(text).split("\n")]
        grid.put_lines(row, self.col, lines, width, self.align, style, self.height)
