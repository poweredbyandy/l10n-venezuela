# Part of Odoo. See LICENSE file for full copyright and licensing details.

VE_CALENDAR_XMLIDS = (
    "l10n_ve_payroll.resource_calendar_ve_diurna_40h",
    "l10n_ve_payroll.resource_calendar_ve_mixta_375h",
    "l10n_ve_payroll.resource_calendar_ve_nocturna_35h",
)

VE_SHARED_COMPANY_MODELS = (
    "hr.payroll.structure",
    "hr.salary.rule",
    "hr.salary.rule.category",
    "l10n_ve.payroll.rule.parameter",
)

DEFAULT_PAID_REST_DAYS = (
    {
        "name": "Saturday rest days",
        "dayofweek": "5",
        "code": "DDESS",
        "sequence": 2,
    },
    {
        "name": "Sunday rest days",
        "dayofweek": "6",
        "code": "DDESD",
        "sequence": 3,
    },
)


def post_init_hook(env):
    _l10n_ve_ensure_calendar_paid_rest_days(env)
    _l10n_ve_share_payroll_master_data(env)


def _l10n_ve_share_payroll_master_data(env):
    """Clear company_id on VE master data so structures/rules are multi-company."""
    Data = env["ir.model.data"].sudo()
    for model in VE_SHARED_COMPANY_MODELS:
        if model not in env:
            continue
        xmlids = Data.search(
            [
                ("module", "=", "l10n_ve_payroll"),
                ("model", "=", model),
            ]
        )
        if not xmlids:
            continue
        records = env[model].browse(xmlids.mapped("res_id")).exists()
        to_share = records.filtered("company_id")
        if to_share:
            to_share.write({"company_id": False})


def _l10n_ve_ensure_calendar_paid_rest_days(env):
    PaidRest = env["resource.calendar.paid.rest.day"]
    for xmlid in VE_CALENDAR_XMLIDS:
        calendar = env.ref(xmlid, raise_if_not_found=False)
        if not calendar:
            continue
        for vals in DEFAULT_PAID_REST_DAYS:
            existing = PaidRest.search(
                [
                    ("calendar_id", "=", calendar.id),
                    ("dayofweek", "=", vals["dayofweek"]),
                ],
                limit=1,
            )
            if existing:
                continue
            PaidRest.create({**vals, "calendar_id": calendar.id})
