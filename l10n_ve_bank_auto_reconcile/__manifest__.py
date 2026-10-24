# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Venezuela Bank Auto Reconcile",
    "summary": (
        "Conciliación bancaria por referencia, en su propia cola "
        "y solo al pulsar el botón"
    ),
    "version": "18.0.1.2.0",
    "category": "Accounting",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "license": "AGPL-3",
    "depends": [
        "account_accountant",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/l10n_ve_bank_reconcile_queue_security.xml",
        "data/ir_cron_data.xml",
        "views/l10n_ve_bank_reconcile_queue_views.xml",
        "views/account_bank_statement_line_views.xml",
    ],
    "installable": True,
}
