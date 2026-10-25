# Part of Odoo. See LICENSE file for full copyright and licensing details.

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    withhold_sso = fields.Boolean(string="Withhold SSO", default=True)
    withhold_faov = fields.Boolean(string="Withhold FAOV", default=True)
    withhold_rpe = fields.Boolean(string="Withhold RPE", default=True)
    withhold_islr = fields.Boolean(string="Withhold ISLR", default=False)
    overtime_day_rate = fields.Monetary(
        string="Day Overtime Rate",
        currency_field="currency_id",
    )
    overtime_night_rate = fields.Monetary(
        string="Night Overtime Rate",
        currency_field="currency_id",
    )
    meal_allowance = fields.Monetary(
        string="Meal Allowance",
        currency_field="currency_id",
        help="If set, overrides company meal ticket amount.",
    )
    profit_sharing_days = fields.Integer(
        string="Profit Sharing Days",
        default=lambda self: self.env.company.profit_sharing_days or 30,
    )
    vacation_bonus_days = fields.Integer(string="Vacation Bonus Days", default=15)
    expired_leave_days = fields.Integer(string="Expired Leave Days", default=0)
    leave_provision_days = fields.Integer(
        string="Leave Provision Days",
        compute="_compute_leave_provision_days",
        store=True,
    )
    seniority_years = fields.Integer(
        string="Seniority Years",
        compute="_compute_seniority",
    )
    seniority_months = fields.Integer(
        string="Seniority Months",
        compute="_compute_seniority",
    )
    seniority_days = fields.Integer(
        string="Seniority Days",
        compute="_compute_seniority",
    )

    @api.depends("date_start", "date_end")
    def _compute_seniority(self):
        today = fields.Date.context_today(self)
        for contract in self:
            start = contract.date_start
            end = contract.date_end or today
            if not start:
                contract.seniority_years = 0
                contract.seniority_months = 0
                contract.seniority_days = 0
                continue
            delta = relativedelta(end, start)
            contract.seniority_years = delta.years
            contract.seniority_months = delta.years * 12 + delta.months
            contract.seniority_days = (end - start).days

    @api.depends("seniority_years")
    def _compute_leave_provision_days(self):
        for contract in self:
            years = contract.seniority_years or 0
            if years <= 0:
                contract.leave_provision_days = 15
            else:
                contract.leave_provision_days = min(15 + max(years - 1, 0), 30)
