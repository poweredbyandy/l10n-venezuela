# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    social_benefit_id = fields.Many2one(
        "l10n_ve.payroll.social.benefit",
        string="Social Benefit Accrual",
        copy=False,
    )
    period_mondays = fields.Integer(
        string="Mondays in Period",
        compute="_compute_period_mondays",
        store=True,
        help="Number of Mondays between date_from and date_to (SSO/RPE base).",
    )

    @api.depends("date_from", "date_to")
    def _compute_period_mondays(self):
        for payslip in self:
            count = 0
            if payslip.date_from and payslip.date_to:
                day = payslip.date_from
                while day <= payslip.date_to:
                    if day.weekday() == 0:
                        count += 1
                    day += timedelta(days=1)
            payslip.period_mondays = count

    @api.model
    def get_worked_day_lines(self, contracts, date_from, date_to):
        res = super().get_worked_day_lines(contracts, date_from, date_to)
        for contract in contracts.filtered(lambda item: item.resource_calendar_id):
            res.extend(
                self._l10n_ve_prepare_rest_day_lines(contract, date_from, date_to)
            )
        return res

    @api.model
    def _l10n_ve_prepare_rest_day_lines(self, contract, date_from, date_to):
        """Build worked-days lines from calendar paid non-working weekdays."""
        day_from, day_to = self._l10n_ve_clamp_period_to_contract(
            contract, date_from, date_to
        )
        if day_from > day_to:
            return []
        calendar = contract.resource_calendar_id
        rest_days = calendar.l10n_ve_paid_rest_day_ids
        if not rest_days:
            return []
        weekday_counts = self._l10n_ve_count_weekdays(day_from, day_to)
        hours_per_day = calendar.hours_per_day or 8.0
        aggregated = {}
        for rest in rest_days:
            count = weekday_counts.get(int(rest.dayofweek), 0)
            if not count:
                continue
            bucket = aggregated.setdefault(
                rest.code,
                {
                    "name": rest.name,
                    "sequence": rest.sequence,
                    "code": rest.code,
                    "number_of_days": 0.0,
                    "contract_id": contract.id,
                },
            )
            bucket["number_of_days"] += float(count)
            bucket["sequence"] = min(bucket["sequence"], rest.sequence)
        lines = []
        for values in aggregated.values():
            values["number_of_hours"] = values["number_of_days"] * hours_per_day
            lines.append(values)
        return lines

    @api.model
    def _l10n_ve_clamp_period_to_contract(self, contract, date_from, date_to):
        day_from = date_from
        day_to = date_to
        if contract.date_start and day_from < contract.date_start:
            day_from = contract.date_start
        if contract.date_end and day_to > contract.date_end:
            day_to = contract.date_end
        return day_from, day_to

    @api.model
    def _l10n_ve_count_weekdays(self, date_from, date_to):
        counts = {weekday: 0 for weekday in range(7)}
        day = date_from
        while day <= date_to:
            counts[day.weekday()] += 1
            day += timedelta(days=1)
        return counts

    def action_payslip_done(self):
        res = super().action_payslip_done()
        self._l10n_ve_process_social_benefits()
        return res

    def _l10n_ve_process_social_benefits(self):
        Benefit = self.env["l10n_ve.payroll.social.benefit"]
        for payslip in self:
            if payslip.social_benefit_id:
                continue
            structure = payslip.struct_id
            force = self.env.context.get("l10n_ve_force_social_benefit")
            if not force and not structure.process_social_benefits:
                continue
            benefit = Benefit.create(
                {
                    "name": payslip.number or payslip.name,
                    "employee_id": payslip.employee_id.id,
                    "company_id": payslip.company_id.id,
                    "date": payslip.date_to,
                    "amount": 0.0,
                    "balance": 0.0,
                    "benefit_type": "accrual",
                    "source_payslip_id": payslip.id,
                }
            )
            payslip.social_benefit_id = benefit.id

    def action_payslip_cancel(self):
        for payslip in self:
            if payslip.social_benefit_id:
                payslip.social_benefit_id.unlink()
                payslip.social_benefit_id = False
        return super().action_payslip_cancel()
