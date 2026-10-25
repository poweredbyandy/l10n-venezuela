# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResourceCalendarPaidRestDay(models.Model):
    _name = "resource.calendar.paid.rest.day"
    _description = "Non-working day that counts for salary"
    _order = "dayofweek, id"

    calendar_id = fields.Many2one(
        "resource.calendar",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(required=True)
    dayofweek = fields.Selection(
        [
            ("0", "Monday"),
            ("1", "Tuesday"),
            ("2", "Wednesday"),
            ("3", "Thursday"),
            ("4", "Friday"),
            ("5", "Saturday"),
            ("6", "Sunday"),
        ],
        string="Day of Week",
        required=True,
        index=True,
    )
    code = fields.Char(
        required=True,
        help="Payslip worked-days code used by salary rules (e.g. DDESS, DDESD).",
    )
    sequence = fields.Integer(default=10)

    _sql_constraints = [
        (
            "calendar_dayofweek_uniq",
            "unique(calendar_id, dayofweek)",
            "Each weekday can only be listed once per calendar.",
        ),
    ]

    @api.onchange("dayofweek")
    def _onchange_dayofweek(self):
        defaults = {
            "5": ("Saturday rest days", "DDESS", 2),
            "6": ("Sunday rest days", "DDESD", 3),
        }
        if self.dayofweek in defaults:
            name, code, sequence = defaults[self.dayofweek]
            self.name = name
            self.code = code
            self.sequence = sequence


class ResourceCalendar(models.Model):
    _inherit = "resource.calendar"

    l10n_ve_paid_rest_day_ids = fields.One2many(
        "resource.calendar.paid.rest.day",
        "calendar_id",
        string="Paid Non-Working Days",
        help="Weekdays that are not worked but still count for salary "
        "(e.g. Saturday/Sunday rest). They generate payslip worked-days "
        "lines with the given code.",
    )
