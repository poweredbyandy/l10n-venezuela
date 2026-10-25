import re

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

    def _l10n_ve_fiscal_address(self):
        self.ensure_one()
        parts = [
            self.street,
            self.street2,
            self.city,
            self.state_id.name,
            self.zip,
        ]
        return ", ".join(part.strip() for part in parts if part and str(part).strip())

    def _l10n_ve_format_rif_seniat(self):
        self.ensure_one()
        prefix_vat = (self.prefix_vat or "").strip().upper()
        partner_vat = (self.vat or "").strip().upper()
        raw_rif = partner_vat
        if prefix_vat and not partner_vat.startswith(prefix_vat):
            raw_rif = f"{prefix_vat}{partner_vat}"

        normalized = re.sub(r"[^A-Z0-9]", "", raw_rif)
        if not normalized:
            return ""

        first_alpha = next((char for char in normalized if char.isalpha()), "")
        digits = "".join(char for char in normalized if char.isdigit())
        return f"{first_alpha}{digits}" if first_alpha else digits

    @api.model
    def _l10n_ve_sql_rif_seniat(self, partner_alias="p"):
        return f"""UPPER(
            REGEXP_REPLACE(COALESCE({partner_alias}.vat, ''), '[^A-Za-z0-9]', '', 'g')
        )"""

    @api.model
    def _l10n_ve_get_islr_applicable_type_person_ids(self):
        return (
            self.env["payment.concept.line"]
            .sudo()
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
