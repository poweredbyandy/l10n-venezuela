{
    "name": "Venezuela Stock Fleet",
    "summary": "Use the company fleet on Venezuelan dispatch guides",
    "version": "18.0.1.0.0",
    "category": "Inventory/Localizations",
    "countries": ["ve"],
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "AGPL-3",
    "depends": [
        "l10n_ve_stock",
        "fleet",
        "stock_picking_batch",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_picking_batch_views.xml",
    ],
    "installable": True,
    "application": False,
}
