# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela SENIAT - Auditor User",
    "summary": "Read-only user for SENIAT auditors",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "version": "18.0.1.0.0",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Accounting/Localizations",
    "depends": ["l10n_ve_seniat"],
    "data": [
        "data/res_users_seniat.xml",
    ],
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "license": "AGPL-3",
    "installable": True,
}
