# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - Journal Dashboard",
    "summary": "Show Venezuelan invoice indicators on the accounting dashboard",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "version": "18.0.1.0.0",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "category": "Accounting/Localizations",
    "depends": ["account", "web"],
    "assets": {
        "web.assets_backend": [
            "l10n_ve_journal_dashboard/static/src/components/invoice_dashboard/"
            "invoice_dashboard.esm.js",
            "l10n_ve_journal_dashboard/static/src/components/invoice_dashboard/"
            "invoice_dashboard.xml",
            "l10n_ve_journal_dashboard/static/src/views/account_dashboard_kanban/"
            "account_dashboard_kanban.esm.js",
            "l10n_ve_journal_dashboard/static/src/views/account_dashboard_kanban/"
            "account_dashboard_kanban.xml",
            "l10n_ve_journal_dashboard/static/src/scss/invoice_dashboard.scss",
        ],
    },
    "license": "AGPL-3",
    "installable": True,
}
