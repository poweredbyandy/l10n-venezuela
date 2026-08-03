# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from odoo.addons.l10n_ve_auditlog.hooks import (
    _table_exists,
    _validate_table_name,
    install_db_audit_triggers,
    uninstall_db_audit_triggers,
)


class L10nVeDbAuditTable(models.Model):
    _name = "l10n.ve.db.audit.table"
    _description = "PostgreSQL Audited Table"
    _order = "table_name"

    name = fields.Char(compute="_compute_name", store=True)
    table_name = fields.Char(required=True, index=True)
    model_id = fields.Many2one("ir.model", string="Odoo Model")
    active = fields.Boolean(default=True)
    trigger_installed = fields.Boolean(readonly=True)

    _sql_constraints = [
        (
            "table_name_uniq",
            "unique(table_name)",
            "Each PostgreSQL table can only be configured once.",
        ),
    ]

    @api.depends("table_name", "model_id")
    def _compute_name(self):
        for record in self:
            if record.model_id:
                record.name = record.model_id.name
            else:
                record.name = record.table_name or ""

    @api.constrains("table_name")
    def _check_table_name(self):
        for record in self:
            try:
                _validate_table_name(record.table_name)
            except ValueError as err:
                raise UserError(str(err)) from err
            if not _table_exists(self.env.cr, record.table_name):
                raise UserError(
                    _("PostgreSQL table %s does not exist in this database.")
                    % record.table_name
                )

    @api.model
    def init(self):
        super().init()
        if self.search_count([]):
            install_db_audit_triggers(self.env)

    def action_install_triggers(self):
        install_db_audit_triggers(self.env)
        return True

    def action_uninstall_triggers(self):
        uninstall_db_audit_triggers(self.env)
        return True
