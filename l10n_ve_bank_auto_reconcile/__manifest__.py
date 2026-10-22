# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Venezuela Bank Auto Reconcile",
    "summary": "Conciliación bancaria por referencia, en tandas y solo al pulsar el botón",
    "version": "18.0.1.0.0",
    "category": "Accounting",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "license": "AGPL-3",
    "depends": [
        "account_accountant",
        "queue_job",
    ],
    "data": [
        "data/ir_cron_data.xml",
        "views/account_bank_statement_line_views.xml",
    ],
    "installable": True,
}
