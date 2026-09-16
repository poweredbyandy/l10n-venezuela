import logging
import tempfile
from functools import lru_cache
from pathlib import Path

from markupsafe import Markup, escape

_logger = logging.getLogger(__name__)
try:
    from escapy.commons import EMBEDDED_CONFIG_FILE
    from escapy.config_parser import build_parser_params, load_config
    from escapy.fonts import setup_fonts
    from escapy.parser import ESCParser
    from escapy.printer_profile import get_printer_profile
except ImportError as err:
    ESCParser = None
    _logger.debug("Cannot `import escapy`: %s", err)

ESC = b"\x1b"
ESC_INIT = ESC + b"@"
ESC_DRAFT = ESC + b"x\x00"
ESC_NLQ = ESC + b"x\x01"
ESC_BOLD_ON = ESC + b"E"
ESC_BOLD_OFF = ESC + b"F"
ESC_DOUBLE_STRIKE_ON = ESC + b"G"
ESC_DOUBLE_STRIKE_OFF = ESC + b"H"
ESC_WIDE_ON = ESC + b"W\x01"
ESC_WIDE_OFF = ESC + b"W\x00"
ESC_UNDERLINE_ON = ESC + b"-\x01"
ESC_UNDERLINE_OFF = ESC + b"-\x00"
ESC_CHAR_TABLE_GRAPHIC = ESC + b"t\x01"
ESC_FONT_RESTORE = ESC + b"P" + ESC + b"2"
CONDENSED_OFF = b"\x12"
FORM_FEED = b"\x0c"

CPI_ESC_P = {
    "10": ESC + b"P",
    "12": ESC + b"M",
    "15": ESC + b"g",
    "17": ESC + b"P\x0f",
    "20": ESC + b"M\x0f",
}
CPI_CHARS_PER_INCH = {"10": 10.0, "12": 12.0, "15": 15.0, "17": 17.14, "20": 20.0}
LPI_ESC_P = {"6": ESC + b"2", "8": ESC + b"0"}
PRINT_QUALITY_ESC_P = {
    "draft": ESC_DRAFT,
    "draft_double": ESC_DRAFT + ESC_DOUBLE_STRIKE_ON,
    "nlq": ESC_NLQ,
}

STYLE_BOLD = 1
STYLE_WIDE = 2
STYLE_UNDERLINE = 8
STYLE_CONT = 4
STYLE_FLAGS = {
    "normal": 0,
    "bold": STYLE_BOLD,
    "wide": STYLE_WIDE,
    "bold_wide": STYLE_BOLD | STYLE_WIDE,
    "underline": STYLE_UNDERLINE,
    "bold_underline": STYLE_BOLD | STYLE_UNDERLINE,
}

ESCAPY_SIDE_MARGIN_PT = 3.0 / 25.4 * 72.0


def encode_text(text):
    return ("" if text is None else str(text)).encode("cp858", errors="replace")


def clip(text, max_len):
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 2] + ".."


def wrap(text, line_width):
    text = (text or "").replace("\r", " ").strip()
    if not text or line_width <= 0:
        return []
    lines = []
    for paragraph in text.split("\n"):
        cur = ""
        for word in paragraph.split():
            test = f"{cur} {word}".strip() if cur else word
            if len(test) <= line_width:
                cur = test
                continue
            if cur:
                lines.append(cur)
            if len(word) <= line_width:
                cur = word
            else:
                for i in range(0, len(word), line_width):
                    lines.append(word[i : i + line_width])
                cur = ""
        if cur:
            lines.append(cur)
    return lines[:200]


class Grid:
    def __init__(self, rows, width):
        self.rows = rows
        self.width = width
        self.chars = [[" "] * width for _ in range(rows)]
        self.styles = [[0] * width for _ in range(rows)]

    def put(self, row, col, text, width=None, align="left", style=0):
        if row < 0 or row >= self.rows:
            return
        max_w = width if width else (self.width - col)
        if max_w <= 0:
            return
        cells_per_char = 2 if style & STYLE_WIDE else 1
        text = clip("" if text is None else str(text), max_w // cells_per_char)
        if not text:
            return
        used = len(text) * cells_per_char
        if align == "right":
            start = col + (max_w - used)
        elif align == "center":
            start = col + (max_w - used) // 2
        else:
            start = col
        line = self.chars[row]
        style_line = self.styles[row]
        for index, char in enumerate(text):
            pos = start + index * cells_per_char
            if not 0 <= pos < len(line):
                continue
            line[pos] = char
            style_line[pos] = style
            if cells_per_char == 2 and pos + 1 < len(line):
                line[pos + 1] = ""
                style_line[pos + 1] = style | STYLE_CONT

    def put_lines(self, row, col, lines, width=None, align="left", style=0, max_lines=1):
        for index, line in enumerate(lines[: max(1, max_lines)]):
            self.put(row + index, col, line, width, align, style)

    def text_lines(self):
        return ["".join(char or " " for char in row) for row in self.chars]

    def encode_line(self, row_index):
        buf = bytearray()
        state = 0
        for char, style in zip(self.chars[row_index], self.styles[row_index]):
            if style & STYLE_CONT:
                continue
            style &= ~STYLE_CONT
            if style != state:
                for flag, on, off in (
                    (STYLE_BOLD, ESC_BOLD_ON, ESC_BOLD_OFF),
                    (STYLE_WIDE, ESC_WIDE_ON, ESC_WIDE_OFF),
                    (STYLE_UNDERLINE, ESC_UNDERLINE_ON, ESC_UNDERLINE_OFF),
                ):
                    if (style & flag) != (state & flag):
                        buf += on if style & flag else off
                state = style
            buf += encode_text(char)
        if state & STYLE_BOLD:
            buf += ESC_BOLD_OFF
        if state & STYLE_WIDE:
            buf += ESC_WIDE_OFF
        if state & STYLE_UNDERLINE:
            buf += ESC_UNDERLINE_OFF
        return bytes(buf)

    def html_row(self, row_index):
        parts = []
        run_style = None
        run_chars = []
        for char, style in zip(self.chars[row_index], self.styles[row_index]):
            if style & STYLE_CONT:
                continue
            if style != run_style:
                parts.append(_html_run("".join(run_chars), run_style or 0))
                run_style = style
                run_chars = []
            run_chars.append(char or " ")
        parts.append(_html_run("".join(run_chars), run_style or 0))
        return Markup("").join(parts)


def _html_run(text, style):
    if not text:
        return Markup("")
    if style & STYLE_WIDE:
        body = Markup("").join(
            Markup('<span class="o_escp_w">%s</span>') % char for char in text
        )
    else:
        body = escape(text)
    if style & STYLE_UNDERLINE:
        body = Markup('<span class="o_escp_u">%s</span>') % body
    if style & STYLE_BOLD:
        body = Markup('<span class="o_escp_b">%s</span>') % body
    return body


def ruler_lines(width):
    tens = "".join(
        str((col // 10) % 10) if col % 10 == 0 and col else " " for col in range(width)
    )
    units = "".join(str(col % 10) for col in range(width))
    return [tens, units]


def pages_to_html(pages):
    if not pages:
        return Markup("")
    width = pages[0].width
    gutter = Markup('<span class="o_escp_gutter">%s</span>')
    lines = [gutter % ("    " + ruler) for ruler in ruler_lines(width)]
    for page_index, grid in enumerate(pages):
        if page_index:
            lines.append(gutter % ("--- " + "-" * width))
        for row_index in range(grid.rows):
            lines.append(gutter % f"{row_index + 1:>3} " + grid.html_row(row_index))
    return (
        Markup('<pre class="o_l10n_ve_escp_preview">')
        + Markup("\n").join(lines)
        + Markup("</pre>")
    )


def page_length_lines(spec, grid_rows):
    height_in = float(spec.get("paper_height_in") or 0.0)
    lpi = float(spec.get("lpi") or 6)
    if height_in > 0:
        return min(127, max(grid_rows, int(round(height_in * lpi))))
    return min(127, max(1, grid_rows + 2))


def pages_to_escp(pages, spec, final_form_feed=True):
    buf = bytearray()
    buf += ESC_INIT
    buf += ESC_BOLD_OFF + ESC_WIDE_OFF + ESC_UNDERLINE_OFF + ESC_DOUBLE_STRIKE_OFF
    buf += PRINT_QUALITY_ESC_P.get(spec.get("quality"), PRINT_QUALITY_ESC_P["draft_double"])
    buf += CPI_ESC_P.get(str(spec.get("cpi")), CPI_ESC_P["17"])
    buf += LPI_ESC_P.get(str(spec.get("lpi")), LPI_ESC_P["6"])
    buf += ESC_CHAR_TABLE_GRAPHIC
    rows = max((grid.rows for grid in pages), default=1)
    buf += ESC + b"C" + bytes([page_length_lines(spec, rows)])
    for index, grid in enumerate(pages):
        for row_index in range(grid.rows):
            buf += grid.encode_line(row_index) + b"\n"
        if final_form_feed or index < len(pages) - 1:
            buf += FORM_FEED
    buf += ESC_BOLD_OFF + ESC_WIDE_OFF + ESC_UNDERLINE_OFF + ESC_DOUBLE_STRIKE_OFF
    buf += ESC_FONT_RESTORE
    buf += CONDENSED_OFF
    return bytes(buf)


def escapy_available():
    return ESCParser is not None


@lru_cache(maxsize=1)
def _escapy_setup():
    config = load_config(EMBEDDED_CONFIG_FILE)
    return (
        get_printer_profile(config),
        setup_fonts(config),
        build_parser_params(config),
    )


def pages_to_pdf(pages, spec):
    return escp_to_pdf(pages_to_escp(pages, spec, final_form_feed=False), spec)


def escp_to_pdf(raw, spec):
    if not escapy_available():
        return False
    profile, fonts, base_params = _escapy_setup()
    params = dict(base_params)
    width_in = float(spec.get("paper_width_in") or 8.5)
    height_in = float(spec.get("paper_height_in") or 11.0)
    params.update(
        {
            "pins": int(spec.get("pins") or 9),
            "single_sheets": False,
            "printable_area_margins_mm": (0.0, 0.0, 3.0, 3.0),
            "page_size": (
                width_in * 72.0 + 2 * ESCAPY_SIDE_MARGIN_PT,
                height_in * 72.0,
            ),
        }
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "preview.pdf"
        params["userdef_db_filepath"] = str(Path(tmpdir) / "user_defined_mapping.json")
        try:
            ESCParser(
                raw,
                profile,
                available_fonts=fonts,
                output_file=str(output),
                **params,
            )
            return output.read_bytes()
        except (Exception, SystemExit):
            _logger.warning("escapy could not render the ESC/P preview", exc_info=True)
            return False
