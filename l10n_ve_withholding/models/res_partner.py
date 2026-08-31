from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    withholding_type_id = fields.Many2one(
        "account.withholding.type",
        string="Withholding Type",
        domain=[("state", "=", True)],
        tracking=True,
        default=lambda self: self.env[
            "account.withholding.type"
        ]._get_default_withholding_type_id(),
    )

    iva_account = fields.Many2one("account.account", string="IVA Account")

    islr_account = fields.Many2one("account.account", string="ISLR Account")

    type_person_id = fields.Many2one(
        "type.person",
        "Type Person",
        store=True,
        tracking=True,
        default=lambda self: self.env["type.person"]._get_default_type_person_id(),
    )

    def _l10n_ve_get_withholding_type(self):
        self.ensure_one()
        return self.withholding_type_id

    @api.model
    def _l10n_ve_get_islr_applicable_type_person_ids(self):
        return (
            self.env["payment.concept.line"]
            .search([("payment_concept_id.status", "=", True)])
            .mapped("type_person_id")
            .filtered("state")
            .ids
        )

    @api.model
    def _l10n_ve_islr_supplier_partner_domain(self):
        type_person_ids = self._l10n_ve_get_islr_applicable_type_person_ids()
        return [
            ("parent_id", "=", False),
            ("supplier_rank", ">", 0),
            ("type_person_id", "in", type_person_ids or [0]),
        ]

    @api.model
    def _prepare_create_values(self, vals_list):
        vals_list = super()._prepare_create_values(vals_list)
        default_type_person_id = self.env["type.person"]._get_default_type_person_id()
        default_withholding_type_id = self.env[
            "account.withholding.type"
        ]._get_default_withholding_type_id()
        for vals in vals_list:
            if default_type_person_id and "type_person_id" not in vals:
                vals["type_person_id"] = default_type_person_id
            if default_withholding_type_id and "withholding_type_id" not in vals:
                vals["withholding_type_id"] = default_withholding_type_id
        return vals_list

    economic_activity_id = fields.Many2one(
        "economic.activity", "Default Economic Activity", store=True, tracking=True
    )
