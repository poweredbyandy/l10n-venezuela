# This module is adapted from ADHOC module: https://github.com/ingadhoc/product/tree/18.0/product_currency
{
    "name": "Product Currency",
    "version": "18.0.1.1.0",
    "category": "Products",
    "sequence": 10,
    "summary": "Select sales and cost currencies on product templates",
    "author": "Andyengit,Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-venezuela",
    "license": "LGPL-3",
    "images": [],
    "depends": [
        "product",
    ],
    "data": [
        "security/product_currency_security.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/product_template_views.xml",
        "wizards/product_currency_migrate_views.xml",
    ],
    "demo": [],
    "installable": True,
    "auto_install": False,
    "application": False,
}
