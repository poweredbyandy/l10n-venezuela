{
    "name": "Venezuela EDI Dispatch Guides",
    "summary": "Digital invoicing flow for Venezuelan dispatch guides",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "AGPL-3",
    "countries": ["ve"],
    "depends": [
        "l10n_ve_edi",
        "l10n_ve_stock",
    ],
    "data": [
        "views/stock_picking_views.xml",
    ],
    "installable": True,
    "auto_install": True,
    "application": False,
}
