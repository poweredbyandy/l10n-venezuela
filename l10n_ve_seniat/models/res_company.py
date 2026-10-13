from odoo import api, fields, models
from odoo.tools import SQL

from .account_journal import VE_JOURNAL_EMISSION_CODES


class ResCompany(models.Model):
    _inherit = "res.company"

    def _l10n_ve_invoice_tag_include_igtf_notice(self):
        """Indica si la factura debe mostrar aviso de IGTF.

        Returns
        -------
        bool

        Notes
        -----
        Providencia SNAT/2022/000013: IGTF 3% en operaciones en divisas.
        """

        self.ensure_one()
        return bool(self.taxpayer_type and self.taxpayer_type != "ordinary")

    def _l10n_ve_emission_medium_codes(self):
        """Return the emission medium codes used by the company sale journals."""
        self.ensure_one()
        journals = (
            self.env["account.journal"]
            .sudo()
            .search(
                [
                    ("company_id", "=", self.id),
                    ("type", "=", "sale"),
                    ("l10n_ve_emission_medium", "!=", False),
                ]
            )
        )
        return tuple(
            sorted(
                {
                    VE_JOURNAL_EMISSION_CODES[medium]
                    for medium in journals.mapped("l10n_ve_emission_medium")
                }
            )
        )

    def _l10n_ve_has_emission_medium(self, code):
        """Return True if a sale journal of the company uses the given code."""
        self.ensure_one()
        return code in self._l10n_ve_emission_medium_codes()

    l10n_ve_on_behalf_of_third_party_enabled = fields.Boolean(
        string="Facturación por cuenta de terceros habilitada",
        default=False,
    )
    l10n_ve_lock_partner_fiscal_data = fields.Boolean(
        string="Bloquear datos fiscales con movimientos",
        default=True,
    )
    l10n_ve_reception_date_payment_term_customer = fields.Boolean(
        string="Use reception date on customer invoices",
        help=(
            "When enabled, payment terms and installment due dates on customer "
            "invoices start from the reception date."
        ),
        default=False,
    )
    l10n_ve_reception_date_payment_term_vendor = fields.Boolean(
        string="Use reception date on vendor bills",
        help=(
            "When enabled, payment terms and installment due dates on vendor "
            "bills start from the reception date."
        ),
        default=False,
    )

    def init(self):
        result = super().init()
        self._l10n_ve_ensure_sql_defaults()
        return result

    @api.model
    def _l10n_ve_ensure_sql_defaults(self):
        cr = self.env.cr
        targets = (
            ("res_company", "res.company"),
            ("product_template", "product.template"),
            ("product_product", "product.product"),
        )
        fallbacks = {
            "boolean": "false",
            "integer": "0",
            "bigint": "0",
            "smallint": "0",
            "numeric": "0",
            "double precision": "0",
            "real": "0",
            "character varying": "''",
            "character": "''",
            "text": "''",
            "date": "'2026-01-01'",
            "timestamp without time zone": "'2026-01-01'",
            "timestamp with time zone": "'2026-01-01'",
        }
        for table_name, model_name in targets:
            cr.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND is_nullable = 'NO'
                  AND column_default IS NULL
                  AND column_name <> 'id'
                """,
                (table_name,),
            )
            model_fields = (
                self.env[model_name]._fields if model_name in self.env else {}
            )
            for column_name, data_type in cr.fetchall():
                sql_default = fallbacks.get(data_type)
                field = model_fields.get(column_name)
                if field is not None:
                    default = field.default
                    if callable(default):
                        default = None
                    if default is not None and default is not False:
                        if field.type == "boolean":
                            sql_default = "true" if default else "false"
                        elif field.type in ("char", "text", "selection", "html"):
                            escaped = str(default).replace("'", "''")
                            sql_default = f"'{escaped}'"
                        elif field.type in ("integer", "float", "monetary"):
                            sql_default = str(default)
                        elif field.type == "many2one":
                            sql_default = str(int(getattr(default, "id", default)))
                if not sql_default:
                    continue
                cr.execute(
                    SQL(
                        "ALTER TABLE %s ALTER COLUMN %s SET DEFAULT %s",
                        SQL.identifier(table_name),
                        SQL.identifier(column_name),
                        SQL(sql_default),
                    )
                )
