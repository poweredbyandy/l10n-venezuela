Band-based report engine for Epson ESC/P dot-matrix printers, in the spirit of the Visual FoxPro report designer.

A report is defined per Odoo model with bands (title, page header, column header, detail, summary, page footer) and objects placed on a character grid (row, column, width, style: bold, double width, underline). Fields are Python expressions evaluated with `safe_eval` against the record (`o`), the detail line (`line`) and helper functions (`money`, `qty`, `date`, `words`...). The engine produces the exact ESC/P byte stream, renders it as a PDF with [EscaPy](https://github.com/ysard/escapy) for a faithful preview, and sends it to the printer through WebUSB.

Each report is published as an `ir.actions.report` of type **ESC/P**, so it appears in the *Print* menu of its model like any PDF report. Legacy FoxPro reports can be imported from their `.frx`/`.frt` files.
