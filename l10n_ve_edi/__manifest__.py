# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela EDI Facturacion Digital",
    "summary": (
        "Base para facturacion digital Venezuela " "(validaciones, payload y flujo)"
    ),
    "version": "18.0.1.13.0",
    "category": "Accounting/Localizations",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "AGPL-3",
    "countries": ["ve"],
    "depends": [
        "l10n_ve_seniat",
        "l10n_ve_withholding",
        "l10n_ve_igtf",
        "l10n_ve_stock",
    ],
    "data": [
        "views/res_config_settings_views.xml",
        "views/account_journal_views.xml",
        "views/account_move_views.xml",
        "views/account_retention_views.xml",
        "views/stock_picking_views.xml",
        "views/portal_templates.xml",
    ],
    "installable": True,
    "application": False,
}
