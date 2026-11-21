from odoo import _, api, fields, models


class PaymentConceptLine(models.Model):
    _name = "payment.concept.line"
    _description = "Payment Concept Line"

    _sql_constraints = [
        ("unique_code", "UNIQUE(code)", "The concept code already exists")
    ]

    pay_from = fields.Float(
        string="Payments greater than:", compute="_compute_pay_from", store=True
    )

    type_person_id = fields.Many2one(
        "type.person",
        string="Type person",
        store=True,
        required=False,
        readonly=True,
        domain=[("state", "=", True)],
        help=(
            "DEPRECATED (see readme/DEPRECATED.md): frozen legacy column "
            "kept as a database backup. Replaced by l10n_ve_person_type + "
            "l10n_ve_islr_category; nothing writes it anymore."
        ),
    )
    l10n_ve_person_type = fields.Selection(
        [
            ("pn_resident", "PN Residente"),
            ("pn_non_resident", "PN No Residente"),
            ("pj_domiciled", "PJ Domiciliada"),
            ("pj_non_domiciled", "PJ No Domiciliada"),
        ],
        string="Person Type",
        index=True,
        help=(
            "Tipo de persona al que aplica esta línea del tarifario "
            "(clave primaria del matching ISLR junto con la categoría)."
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
        default="standard",
        index=True,
        help=(
            "Categoría ISLR a la que aplica esta línea. Las líneas "
            "especiales solo se usan cuando el contacto tiene esa misma "
            "categoría; el resto cae a la línea 'Estándar' del tipo."
        ),
    )
    payment_concept_id = fields.Many2one(
        "payment.concept",
        string="Associated Payment Concept",
        required=True,
        domain=[("status", "=", True)],
        ondelete="cascade",
    )
    percentage_tax_base = fields.Float(string="Percentage Taxable Base")
    tariff_id = fields.Many2one(
        "fees.retention", string="Tariff", domain=[("status", "=", True)]
    )
    code = fields.Char(string="Concept code", required=True)

    @api.onchange("percentage_tax_base")
    def check_value_percentage(self):
        if self.percentage_tax_base > 100:
            return {
                "warning": {
                    "title": _("Error in taxable base percentage field"),
                    "message": _(
                        "the percentage may not exceed 100% on the payment concept line"
                    ),
                },
                "value": {"percentage_tax_base": 0},
            }

    @api.depends("tariff_id.tax_unit_id.value", "tariff_id.amount_subtract")
    def _compute_pay_from(self):
        for record in self:
            if record.tariff_id.amount_subtract:
                record.pay_from = (record.tariff_id.tax_unit_id.value * 1000) / 12
            else:
                record.pay_from = 0
