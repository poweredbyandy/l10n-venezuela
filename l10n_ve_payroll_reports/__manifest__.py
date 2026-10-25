# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - Payroll Reports",
    "summary": "FAOV, ISLR laboral, INCES, MINTRA, IVSS and XLSX declarations",
    "version": "18.0.1.1.0",
    "category": "Payroll",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "license": "AGPL-3",
    "countries": ["ve"],
    "depends": ["l10n_ve_payroll", "l10n_ve_reports"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/declaration_export_wizard_views.xml",
        "views/menus.xml",
    ],
    "external_dependencies": {"python": ["xlsxwriter"]},
    "installable": True,
}
