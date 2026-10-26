# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Venezuela Bank Auto Reconcile",
    "summary": "Conciliación bancaria por referencia, en tandas y solo al pulsar el botón",
    "version": "18.0.1.3.0",
    "category": "Accounting",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "license": "AGPL-3",
    "depends": [
        "account_accountant",
        "queue_job",
        "l10n_ve_payment_closing",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/l10n_ve_default_account_security.xml",
        "data/ir_cron_data.xml",
        "views/account_bank_statement_line_views.xml",
        "views/l10n_ve_default_account_views.xml",
    ],
    "installable": True,
    "post_init_hook": "post_init_hook",
}
