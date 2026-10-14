# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Venezuela - Payment Terminal Closing (Point of Sale)",
    "summary": "Filter terminal closings by Point of Sale payment method",
    "version": "18.0.1.0.0",
    "category": "Accounting/Localizations",
    "website": "https://github.com/OCA/l10n-venezuela",
    "countries": ["ve"],
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "license": "AGPL-3",
    "depends": [
        "l10n_ve_payment_closing",
        "point_of_sale",
    ],
    "data": [
        "views/account_payment_closing_views.xml",
    ],
    "auto_install": True,
    "installable": True,
}
