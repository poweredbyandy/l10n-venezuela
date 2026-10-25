# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrSalaryRule(models.Model):
    _inherit = "hr.salary.rule"

    struct_id = fields.Many2one(
        "hr.payroll.structure",
        string="Salary Structure",
        compute="_compute_struct_id",
        store=True,
        index=True,
    )
    struct_name = fields.Char(
        related="struct_id.name",
        string="Structure",
        store=True,
    )

    def _compute_struct_id(self):
        # hr.payslip.line inherits this model: do not use a real M2M table.
        mapping = {}
        rule_ids = [rid for rid in self.ids if rid]
        if rule_ids:
            self.env.cr.execute(
                """
                SELECT rule_id, MIN(struct_id)
                FROM hr_structure_salary_rule_rel
                WHERE rule_id IN %s
                GROUP BY rule_id
                """,
                (tuple(rule_ids),),
            )
            mapping = dict(self.env.cr.fetchall())
        for rule in self:
            rule.struct_id = mapping.get(rule.id) or False
