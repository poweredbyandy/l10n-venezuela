# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela - Payroll Accounting",
    "summary": "Map Venezuelan payroll rules to SENIAT accounts and provisions",
    "version": "18.0.1.5.1",
    "category": "Payroll",
    "website": "https://github.com/OCA/l10n-venezuela",
    "author": "andyengit, Odoo Community Association (OCA)",
    "maintainers": ["andyengit"],
    "license": "AGPL-3",
    "countries": ["ve"],
    "depends": [
        "payroll_account",
        "l10n_ve_payroll",
        "l10n_ve_seniat",
        "payroll_employee_loan",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/payroll_provision_views.xml",
        "views/hr_payslip_payment_views.xml",
        "views/res_config_settings_views.xml",
        "views/payroll_employee_loan_views.xml",
        "wizard/hr_payslip_payment_register_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
