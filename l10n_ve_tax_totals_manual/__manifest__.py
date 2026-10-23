# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - Manual tax totals",
    "summary": "Edit invoice tax totals in document and company currency",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "version": "18.0.1.1.0",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Accounting/Localizations",
    "depends": [
        "account_currency",
        "l10n_ve_loyalty",
    ],
    "data": [
        "security/l10n_ve_tax_totals_manual_security.xml",
    ],
    "assets": {
        "web.assets_backend": [
            (
                "after",
                "l10n_ve_loyalty/static/src/components/tax_totals/"
                "tax_totals_global_discount.xml",
                "l10n_ve_tax_totals_manual/static/src/components/tax_totals/"
                "tax_totals.xml",
            ),
            (
                "after",
                "account_currency/static/src/components/tax_totals/tax_totals.esm.js",
                "l10n_ve_tax_totals_manual/static/src/components/tax_totals/"
                "tax_totals.esm.js",
            ),
        ],
    },
    "license": "AGPL-3",
    "installable": True,
}
