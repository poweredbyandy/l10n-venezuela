# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - Address",
    "summary": "Venezuelan states, municipalities and parishes for addresses",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "version": "18.0.1.0.0",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Accounting/Localizations",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "data/res.country.state.csv",
        "data/res.country.municipality.csv",
        "data/res.country.parish.csv",
        "views/res_country_municipality_views.xml",
        "views/res_country_parish_views.xml",
        "views/res_partner_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "license": "AGPL-3",
    "installable": True,
}
