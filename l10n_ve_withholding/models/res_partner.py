import re

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    withholding_type_id = fields.Many2one(
        "account.withholding.type",
        string="Withholding Type",
        domain=[("state", "=", True)],
        tracking=True,
        help=(
            "Sin valor por defecto: no todos los contribuyentes están "
            "sujetos a retención."
        ),
    )

    iva_account = fields.Many2one("account.account", string="IVA Account")

    islr_account = fields.Many2one("account.account", string="ISLR Account")

    type_person_id = fields.Many2one(
        "type.person",
        "Type Person",
        store=True,
        readonly=True,
        tracking=False,
        help=(
            "DEPRECATED (see readme/DEPRECATED.md): frozen legacy column "
            "kept as a database backup. Replaced by l10n_ve_person_type + "
            "l10n_ve_islr_category; nothing writes it anymore."
        ),
    )

    l10n_ve_islr_category = fields.Selection(
        [
            ("standard", "Estándar"),
            ("radio_broadcaster", "Emisora de Radio Domiciliada"),
            (
                "financial_institution",
                "Institución Financiera No Domiciliada",
            ),
            ("other", "Otra PJ No Domiciliada"),
        ],
        string="ISLR Category",
        compute="_compute_l10n_ve_islr_category",
        store=True,
        readonly=False,
        precompute=True,
        tracking=False,
        help=(
            "Excepción del tarifario ISLR que no se deriva del RIF ni del "
            "país. Solo aplica a personas jurídicas; se resetea a "
            "'Estándar' cuando el tipo de persona no la admite."
        ),
    )

    @api.model
    def _l10n_ve_normalize_islr_category(self, person_type, category):
        """Reset ISLR categories not valid for the given person type."""
        category = category or "standard"
        if person_type == "pj_domiciled":
            if category not in ("standard", "radio_broadcaster"):
                return "standard"
        elif person_type == "pj_non_domiciled":
            if category not in ("standard", "financial_institution", "other"):
                return "standard"
        else:
            # Natural persons have no ISLR exceptions in the tariff.
            return "standard"
        return category

    @api.depends("l10n_ve_person_type")
    def _compute_l10n_ve_islr_category(self):
        for partner in self:
            partner.l10n_ve_islr_category = (
                self._l10n_ve_normalize_islr_category(
                    partner.l10n_ve_person_type, partner.l10n_ve_islr_category
                )
            )

    @api.onchange("l10n_ve_person_type", "l10n_ve_islr_category")
    def _onchange_l10n_ve_islr_category(self):
        self.l10n_ve_islr_category = self._l10n_ve_normalize_islr_category(
            self.l10n_ve_person_type, self.l10n_ve_islr_category
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

    economic_activity_id = fields.Many2one(
        "economic.activity", "Default Economic Activity", store=True, tracking=True
    )

    @api.model
    def _l10n_ve_islr_supplier_partner_domain(self):
        """Domain of suppliers the ISLR retention flow can classify.

        Primary rule: the partner's person type has at least one active
        concept line (the category always falls back to `standard`, see
        ``_l10n_ve_get_payment_concept_line``). Legacy fallback: concept
        lines not migrated yet (custom ``type.person`` rows) are matched
        through the frozen ``type_person_id``.
        """
        lines = (
            self.env["payment.concept.line"]
            .sudo()
            .search([("payment_concept_id.status", "=", True)])
        )
        person_types = [value for value in lines.mapped("l10n_ve_person_type") if value]
        base_domain = [("parent_id", "=", False), ("supplier_rank", ">", 0)]
        if person_types:
            return base_domain + [("l10n_ve_person_type", "in", person_types)]
        type_person_ids = self._l10n_ve_get_islr_applicable_type_person_ids()
        return base_domain + [("type_person_id", "in", type_person_ids or [0])]
