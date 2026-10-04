# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - RIF/CI Validation",
    "summary": "Validate Venezuelan RIF and identity card numbers with base_vat",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "version": "18.0.1.0.0",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Accounting/Localizations",
    "depends": ["base_vat"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "license": "AGPL-3",
    "installable": True,
}
