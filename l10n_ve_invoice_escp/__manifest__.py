{
    "name": "Venezuela — Factura ESC/P Epson (WebUSB)",
    "version": "18.0.3.0.0",
    "category": "Accounting/Localizations",
    "summary": "Impresión de facturas VE en papel continuo vía WebUSB (ESC/P Epson)",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainer": "andyengit",
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "AGPL-3",
    "depends": ["l10n_ve_seniat", "l10n_ve_escp"],
    "data": [
        "data/l10n_ve_escp_report_invoice_data.xml",
        "views/account_journal_views.xml",
    ],
    "installable": True,
}
