from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

ALIQUOT_TYPE_SELECTION = [
    ("exempt", "E - Exento"),
    ("general", "G - General"),
    ("reduced", "R - Reducido"),
    ("extend", "A - Extendida"),
]


class AccountTaxGroup(models.Model):
    _inherit = "account.tax.group"

    l10n_ve_aliquot_type = fields.Selection(
        selection=ALIQUOT_TYPE_SELECTION,
        string="Alícuota SENIAT",
    )
    l10n_ve_exclude_from_reports = fields.Boolean(
        string="No incluir en reportes",
        default=False,
    )

    _sql_constraints = [
        (
            "l10n_ve_aliquot_type_company_uniq",
            "unique(company_id, l10n_ve_aliquot_type)",
            "No puede existir más de un grupo con el mismo tipo de alícuota.",
        ),
    ]

    @api.constrains(
        "l10n_ve_aliquot_type",
        "l10n_ve_exclude_from_reports",
        "country_id",
    )
    def _check_l10n_ve_aliquot_config(self):
        for group in self.filtered(lambda g: g.country_code == "VE"):
            if group.l10n_ve_exclude_from_reports and group.l10n_ve_aliquot_type:
                raise ValidationError(
                    _(
                        "Un grupo no puede tener tipo de alícuota y estar "
                        "marcado como no incluir en reportes."
                    )
                )

    def _l10n_ve_get_report_type(self):
        self.ensure_one()
        if self.l10n_ve_aliquot_type:
            return self.l10n_ve_aliquot_type
        if self.l10n_ve_exclude_from_reports:
            return "exempt"
        return None

    def _l10n_ve_get_representative_tax(self, type_tax_use):
        self.ensure_one()
        return self.env["account.tax"].search(
            [
                ("tax_group_id", "=", self.id),
                ("type_tax_use", "=", type_tax_use),
                ("amount_type", "=", "percent"),
            ],
            limit=1,
        )

    def _l10n_ve_get_tax_rate(self, type_tax_use="sale"):
        self.ensure_one()
        tax = self._l10n_ve_get_representative_tax(type_tax_use)
        if tax:
            return float(tax.amount)
        return 0.0

    @api.model
    def _l10n_ve_get_report_tax_groups(self, company):
        if not company:
            return self.env["account.tax.group"]
        return self.search(
            [
                ("company_id", "=", company.id),
                ("country_id.code", "=", "VE"),
                "|",
                ("l10n_ve_exclude_from_reports", "=", True),
                ("l10n_ve_aliquot_type", "!=", False),
            ],
            order="sequence, id",
        )

    @api.model
    def _l10n_ve_build_tax_config(self, company):
        tax_config = {}
        typed_report_types = set()
        for group in self._l10n_ve_get_report_tax_groups(company):
            report_type = group._l10n_ve_get_report_type()
            if not report_type or report_type in typed_report_types:
                continue
            tax_config[report_type] = group.id
            if group.l10n_ve_aliquot_type:
                typed_report_types.add(report_type)
        return tax_config

    @api.model
    def _l10n_ve_get_exempt_group(self, company):
        domain = [
            ("company_id", "=", company.id),
            ("country_id.code", "=", "VE"),
        ]
        return self.search(
            domain + [("l10n_ve_aliquot_type", "=", "exempt")], limit=1
        ) or self.search(
            domain + [("l10n_ve_exclude_from_reports", "=", True)],
            order="sequence, id",
            limit=1,
        )

    @api.model
    def _l10n_ve_get_exempt_tax(self, company, type_tax_use):
        group = self._l10n_ve_get_exempt_group(company)
        if group:
            return group._l10n_ve_get_representative_tax(type_tax_use)
        return self.env["account.tax"]

    @api.model
    def _l10n_ve_get_exent_sale_tax(self, company):
        tax = self.sudo()._l10n_ve_get_exempt_tax(company, "sale")
        if tax:
            return tax
        return (
            self.env["account.tax"]
            .sudo()
            .search(
                [
                    ("company_id", "parent_of", company.id),
                    ("type_tax_use", "=", "sale"),
                    ("amount", "=", 0.0),
                ],
                limit=1,
            )
        )

    @api.model
    def _l10n_ve_get_exent_purchase_tax(self, company):
        tax = self.sudo()._l10n_ve_get_exempt_tax(company, "purchase")
        if tax:
            return tax
        return (
            self.env["account.tax"]
            .sudo()
            .search(
                [
                    ("company_id", "parent_of", company.id),
                    ("type_tax_use", "=", "purchase"),
                    ("amount", "=", 0.0),
                ],
                limit=1,
            )
        )

    @api.model
    def _l10n_ve_get_tax_rate_for_type(self, company, aliquot_type, type_tax_use):
        tax_group_id = self._l10n_ve_build_tax_config(company).get(aliquot_type)
        if not tax_group_id:
            return 0.0
        return self.browse(tax_group_id)._l10n_ve_get_tax_rate(type_tax_use)
