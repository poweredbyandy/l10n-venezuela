# Part of Odoo. See LICENSE file for full copyright and licensing details.

VE_CALENDAR_XMLIDS = (
    "l10n_ve_payroll.resource_calendar_ve_diurna_40h",
    "l10n_ve_payroll.resource_calendar_ve_mixta_375h",
    "l10n_ve_payroll.resource_calendar_ve_nocturna_35h",
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
