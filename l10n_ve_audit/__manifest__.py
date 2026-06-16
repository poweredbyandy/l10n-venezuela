# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    "name": "Venezuela SENIAT - Auditoria",
    "version": "18.0.1.1.1",
    "author": "Anderson Armeya, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-venezuela",
    "category": "Tools",
    "depends": ["auditlog", "l10n_ve_seniat", "l10n_ve_withholding", "l10n_ve_reports"],
    "data": [
        "security/ir.model.access.csv",
        "views/menus.xml",
        "views/http_session_views.xml",
        "views/login_attempt_views.xml",
        "views/validation_exception_views.xml",
        "views/account_report_access_views.xml",
        "data/auditlog_rule_data.xml",
    ],
    "license": "AGPL-3",
    "installable": True,
}
