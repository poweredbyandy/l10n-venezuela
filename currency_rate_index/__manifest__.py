# Copyright 2026 Anderson Armeya
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Currency Rate Index",
    "summary": "Direct exchange rates against a configurable index currency",
    "version": "18.0.1.4.1",
    "category": "Accounting/Accounting",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "AGPL-3",
    "images": [],
    "depends": [
        "account",
        "purchase",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_currency_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
