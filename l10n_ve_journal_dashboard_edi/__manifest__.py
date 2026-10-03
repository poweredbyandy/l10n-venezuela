# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - Journal Dashboard EDI",
    "summary": "Show unsent digital documents on the Venezuelan journal dashboard",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "version": "18.0.1.0.0",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Accounting/Localizations",
    "depends": ["l10n_ve_journal_dashboard", "l10n_ve_edi"],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_journal_dashboard_edi/static/src/components/unsent_dashboard/"
            "unsent_dashboard.esm.js",
            "l10n_ve_journal_dashboard_edi/static/src/components/unsent_dashboard/"
            "unsent_dashboard.xml",
            "l10n_ve_journal_dashboard_edi/static/src/components/invoice_dashboard/"
            "invoice_dashboard.esm.js",
            "l10n_ve_journal_dashboard_edi/static/src/views/account_dashboard_kanban/"
            "account_dashboard_kanban.esm.js",
            "l10n_ve_journal_dashboard_edi/static/src/views/account_dashboard_kanban/"
            "account_dashboard_kanban.xml",
            "l10n_ve_journal_dashboard_edi/static/src/scss/unsent_dashboard.scss",
        ],
    },
    "license": "AGPL-3",
    "auto_install": True,
    "installable": True,
}
