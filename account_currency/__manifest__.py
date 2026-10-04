# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Account Currency",
    "summary": "Company currency amounts and exchange rates on invoices",
    "website": "https://github.com/OCA/l10n-venezuela",
    "version": "18.0.1.1.0",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Accounting/Accounting",
    "depends": [
        "account",
        "mail",
    ],
    "data": [
        "views/res_currency_views.xml",
        "views/account_move_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "account_currency/static/src/components/tax_totals/tax_totals.esm.js",
            "account_currency/static/src/components/tax_totals/tax_totals.xml",
        ],
    },
    "license": "AGPL-3",
    "installable": True,
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
}
