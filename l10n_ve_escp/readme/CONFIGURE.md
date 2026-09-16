Activate developer mode and go to **Settings > Technical > Reporting > ESC/P reports**.

Create a report:

1. Pick the **Model**, the printer pitch (**CPI**, **LPI**), the **printable width** and the **form height**. The height defines the page length sent to the printer so form feeds land on the next pre-printed form.
2. Add **bands**: page header, column header, detail (set *Detail records*, e.g. `o.invoice_line_ids`, and optionally a fixed number of rows per page), summary and page footer. Band heights are in lines; the detail height is lines per record.
3. Add **objects** to each band: labels (fixed text, line breaks allowed), fields (Python expression, optional format monetary/decimal/integer/date) and horizontal lines. Each object has row and column relative to its band, width, alignment, style (bold, double width, underline), optional word wrap and a *Print if* condition.
4. Choose a **sample record** on the *Preview* tab to see the exact ESC/P output rendered as PDF, or use **Print test** to send it to the printer without side effects.
5. Click **Diseñador** to open the visual designer: bands are shown as stacked strips over the character grid (one cell per printer character), objects as boxes you can drag, resize from their right and bottom edges, move between bands, duplicate (Ctrl+D), delete (Supr) and nudge with the arrow keys (Shift+arrows resizes). The side panel edits the selected object or band, *Datos de muestra* shows the values of the sample record instead of the expressions, and the header reports how many of the form lines are used. Save with the button or Ctrl+S; Ctrl+Z undoes.

Expressions can use `o` (record), `line` (detail record), `pl` (detail record with optional shortcuts), `line_no`, `page`, `page_count`, `user`, `company`, `today`, and the helpers `money(amount, currency)`, `num(amount, digits)`, `qty(amount)`, `date(value, pattern)`, `datetime_fmt(value, pattern)`, `words(amount, currency)`, `field(record, 'partner_id.name')`, `upper()`, `lower()`, `wrap(text, width)`.

Any stored or computed field on the model is available through dotted paths, for example `o.partner_id.name`, `line.price_subtotal`, `line.product_id.default_code` or `pl.price_subtotal_currency`. Use the object format (monetary, date...) when you need formatting; shortcuts added by business modules (such as `pl.desc` on invoices) override the raw field name.

Business modules may add more names by implementing `_l10n_ve_escp_eval_context(report)` and `_l10n_ve_escp_line_eval_context(report, line)` on the model, override layout at print time with `_l10n_ve_escp_layout_params(report)` (`margin_top_lines`, `detail_rows`), and hooks `_l10n_ve_escp_check_print(report)` / `_l10n_ve_escp_after_print(report)`.

To import a Visual FoxPro report use **Settings > Technical > Reporting > Import FoxPro report**, upload the `.frx` and `.frt` files and choose the target model. Bands and positions are converted to the character grid; FoxPro expressions without a known equivalent are kept as quoted text so you can replace them.
