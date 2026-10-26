# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class L10nVeDefaultAccount(models.Model):
    _name = "l10n_ve.default.account"
    _description = "Cuentas por defecto"
    _check_company_auto = True

    name = fields.Char(default="Cuentas por defecto")
    company_id = fields.Many2one(
        comodel_name="res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    commission_account_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de comisiones",
        check_company=True,
        domain="[('deprecated', '=', False), ('internal_group', '=', 'expense')]",
        help="Cuenta de gasto para las líneas del extracto cuya etiqueta "
        "contiene COMISION. La conciliación automática contabiliza ahí el "
        "monto completo, sin crear un pago.",
    )

    _sql_constraints = [
        (
            "company_uniq",
            "unique(company_id)",
            "Ya existe una configuración de cuentas por defecto para esta compañía.",
        )
    ]

    @api.depends("company_id")
    def _compute_display_name(self):
        for record in self:
            record.display_name = record.name or _("Cuentas por defecto")

    def init(self):
        self.env.cr.execute(
            """
            UPDATE l10n_ve_default_account
               SET name = 'Cuentas por defecto'
             WHERE name IS NULL OR name = ''
            """
        )

    @api.model
    def commission_account_for(self, company):
        return self.search(
            [("company_id", "=", company.id)], limit=1
        ).commission_account_id

    @api.model
    def action_open_default_accounts(self):
        company = self.env.company
        record = self.search([("company_id", "=", company.id)], limit=1)
        if not record:
            record = self.create({"company_id": company.id})
        return {
            "type": "ir.actions.act_window",
            "name": _("Cuentas por defecto"),
            "res_model": self._name,
            "view_mode": "form",
            "res_id": record.id,
            "target": "current",
            "context": {"create": False, "delete": False},
        }
