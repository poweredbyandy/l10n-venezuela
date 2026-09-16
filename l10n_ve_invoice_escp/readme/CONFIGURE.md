1. Configure the sales journal with **Free form** emission and **Continuous** print medium (module `l10n_ve_seniat`).
2. Optionally pick a **Reporte ESC/P** on the journal. Empty uses the report shipped with the module, **Factura forma libre carta (FoxPro factur01, 17 CPI)**.
3. On the **talonario** linked to the journal (Accounting > Configuration > Talonarios), set **Máximo de líneas por factura** and **Líneas de margen (factura ESC/P)**. At print time those values override the report defaults: the margin becomes blank lines before the header and the maximum becomes the number of product rows per page on continuous paper.
4. To adapt field positions, go to **Accounting > Configuration > Reportes ESC/P**, duplicate the shipped report and edit its bands and objects (row, column, width, style, text or expression). Use a posted invoice as **sample record** to preview the exact printer output including talonario margin and line limits.

Expressions available on `account.move` reports, besides the engine helpers:

- Header: `doc_title`, `doc_label`, `invoice_number`, `emission`, `partner_name`, `partner_vat`, `partner_email`, `partner_phone`, `partner_address`, `client_code`, `seller`, `payment_term`, `origin_document`.
- Detail: any `account.move.line` field via `line.<field>` or `pl.<field>` (for example `line.price_subtotal_currency`, `line.product_id.default_code`). Shortcuts with formatting: `pl.code`, `pl.desc`, `pl.ref`, `pl.brand`, `pl.qty`, `pl.price_unit`, `pl.subtotal`, `pl.price_unit_company_currency`, `pl.price_subtotal_currency`, `pl.subtotal_company_currency`.
- Totals: `tot.doc.<key>` / `tot.comp.<key>` formatted in document and company currency (`exempt`, `gross`, `discount`, `subtotal`, `vat_base`, `vat`, `invoice`, `igtf_base`, `igtf`, `payable`), raw amounts in `tot.doc_amount` / `tot.comp_amount`, plus `vat_percent`, `igtf_percent`, `discount_percent`, `dual_currency`, `doc_currency`, `comp_currency`.
- Footer: `count_articles`, `count_qty`, `exchange_rate`, `amount_words`, `stamp`.

The module also registers a FoxPro expression map so **Import FoxPro report** converts the original `factur01.frx` fields (`nombrecli`, `totalfinal`...) to these names automatically.
