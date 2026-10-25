# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrPayrollStructure(models.Model):
    _inherit = "hr.payroll.structure"

    company_id = fields.Many2one(required=False)

    process_social_benefits = fields.Boolean(
        string="Process Social Benefits",
        help="When enabled, confirmed payslips accrue social benefits (prestaciones).",
    )
    schedule_pay = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("semi-annually", "Semi-annually"),
            ("annually", "Annually"),
            ("weekly", "Weekly"),
            ("bi-weekly", "Bi-weekly"),
            ("bi-monthly", "Bi-monthly"),
        ],
        string="Suggested Schedule Pay",
        help="Informational schedule for operators (OCA uses contract.schedule_pay).",
    )

    @api.model_create_multi
    def create(self, vals_list):
        structures = super().create(vals_list)
        structures.mapped("rule_ids")._compute_struct_id()
        return structures

    def write(self, vals):
        before = {structure.id: structure.rule_ids.ids for structure in self}
        res = super().write(vals)
        if "rule_ids" in vals:
            rules = self.mapped("rule_ids")
            for structure in self:
                removed = set(before.get(structure.id, [])) - set(structure.rule_ids.ids)
                if removed:
                    rules |= self.env["hr.salary.rule"].browse(list(removed))
            rules._compute_struct_id()
        return res
