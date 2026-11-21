# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - RIF Field Widget",
    "summary": "RIF/CI input widget: kind selector (V/E/J/C/P/G) with automatic dash formatting",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "version": "18.0.1.0.0",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Accounting/Localizations",
    "depends": [
        "l10n_ve_seniat",
    ],
    "data": [
        "views/res_partner_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_rif_widget/static/src/js/rif_field.js",
            "l10n_ve_rif_widget/static/src/xml/rif_field.xml",
            "l10n_ve_rif_widget/static/src/scss/rif_field.scss",
        ],
        "web.assets_unit_tests": [
            "l10n_ve_rif_widget/static/tests/rif_field.test.js",
        ],
    },
    "license": "AGPL-3",
    "installable": True,
}
