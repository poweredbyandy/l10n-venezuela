# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - Journal Dashboard Stock",
    "summary": "Show unfactured dispatch guides on the Venezuelan journal dashboard",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "version": "18.0.1.0.0",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Accounting/Localizations",
    "depends": ["l10n_ve_journal_dashboard", "l10n_ve_stock"],
    "data": [
        "views/stock_picking_views.xml",
    ],
    "license": "AGPL-3",
    "auto_install": True,
    "installable": True,
}
