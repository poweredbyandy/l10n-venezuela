# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Venezuela - Payment Terminal Closing",
    "summary": "Group daily card terminal payments into a single bank entry",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "license": "AGPL-3",
    "depends": ["account"],
    "data": [
        "security/ir.model.access.csv",
        "security/account_payment_closing_security.xml",
        "data/ir_sequence_data.xml",
        "views/account_payment_closing_views.xml",
        "views/account_payment_views.xml",
    ],
    "installable": True,
}
