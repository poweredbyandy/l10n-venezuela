# Copyright 2026 Anderson Armeya
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCurrencyRateIndex(models.Model):
    _name = "res.currency.rate.index"
    _description = "Currency Index Rate"
    _order = "name desc"
    _check_company_domain = models.check_company_domain_parent_of

    name = fields.Date(
        string="Date",
        required=True,
        index=True,
        default=fields.Date.context_today,
    )
    rate = fields.Float(
        string="Index per Unit",
        digits=0,
        required=True,
        default=1.0,
        help=(
            "Unidades de la moneda índice por una unidad de esta moneda. "
            "Ejemplo con índice USD: 1 CNY = 0.14 USD."
        ),
    )
    inverse_rate = fields.Float(
        string="Unit per Index",
        digits=0,
        compute="_compute_inverse_rate",
        inverse="_inverse_inverse_rate",
        help=(
            "Unidades de esta moneda por una unidad de la moneda índice. "
            "Ejemplo con índice USD: 1 USD = 7.14 CNY."
        ),
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company.root_id,
    )

    _sql_constraints = [
        (
            "unique_name_per_day",
            "unique (name, currency_id, company_id)",
            "Only one index rate per day allowed!",
        ),
        (
            "currency_rate_index_check",
            "CHECK (rate > 0)",
            "The index rate must be strictly positive.",
        ),
    ]

    def _sanitize_vals(self, vals):
        vals = dict(vals)
        if "inverse_rate" in vals and "rate" in vals:
            vals.pop("inverse_rate", None)
        elif "inverse_rate" in vals:
            inverse = vals.pop("inverse_rate") or 1.0
            vals["rate"] = 1.0 / inverse
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create([self._sanitize_vals(vals) for vals in vals_list])
        records._sync_native_rate_from_index()
        return records

    def write(self, vals):
        res = super().write(self._sanitize_vals(vals))
        if {"rate", "name", "currency_id", "company_id"} & set(vals):
            self._sync_native_rate_from_index()
        return res

    @api.depends("rate")
    def _compute_inverse_rate(self):
        for rate in self:
            value = rate.rate or 1.0
            rate.inverse_rate = 1.0 / value

    def _inverse_inverse_rate(self):
        for rate in self:
            inverse = rate.inverse_rate or 1.0
            rate.rate = 1.0 / inverse

    @api.onchange("inverse_rate")
    def _onchange_inverse_rate(self):
        for rate in self:
            inverse = rate.inverse_rate or 1.0
            rate.rate = 1.0 / inverse

    @api.onchange("rate")
    def _onchange_rate(self):
        for rate in self:
            value = rate.rate or 1.0
            rate.inverse_rate = 1.0 / value

    @api.constrains("rate")
    def _check_rate(self):
        for rate in self:
            if rate.rate <= 0:
                raise ValidationError(
                    _("The index rate must be strictly positive.")
                )

    @api.constrains("company_id", "currency_id")
    def _check_company_index_currency(self):
        for rate in self:
            company = rate.company_id or self.env.company.root_id
            if not company.currency_index_id:
                raise ValidationError(
                    _(
                        "Configure la moneda índice de la compañía %(company)s "
                        "en Ajustes antes de registrar tasas índice.",
                        company=company.display_name,
                    )
                )

    def _sync_native_rate_from_index(self):
        if self.env.context.get("currency_rate_index_skip_sync"):
            return
        Rate = self.env["res.currency.rate"].with_context(
            currency_rate_index_skip_sync=True
        )
        for rec in self:
            if not rec.rate or not rec.currency_id or not rec.name:
                continue
            company = rec.company_id or self.env.company.root_id
            index_currency = company.currency_index_id
            company_currency = company.currency_id
            if not index_currency or not company_currency:
                continue
            if rec.currency_id in (index_currency, company_currency):
                continue
            if not index_currency._has_native_rate(company, rec.name):
                continue
            index_to_company = index_currency._convert(
                1.0,
                company_currency,
                company,
                rec.name,
                round=False,
            )
            if not index_to_company:
                continue
            # rate = index per unit → company per unit = rate * (company per index)
            inverse_company_rate = rec.rate * index_to_company
            if inverse_company_rate <= 0:
                continue
            company_rate = 1.0 / inverse_company_rate
            existing = Rate.search(
                [
                    ("name", "=", rec.name),
                    ("currency_id", "=", rec.currency_id.id),
                    ("company_id", "=", company.id),
                ],
                limit=1,
            )
            manual_rates = Rate.search(
                [
                    ("currency_id", "=", rec.currency_id.id),
                    ("company_id", "in", (False, company.id)),
                    ("rate_index_synced", "=", False),
                ],
                limit=1,
            )
            vals = {
                "company_rate": company_rate,
                "rate_index_synced": True,
            }
            if existing:
                if existing.rate_index_synced:
                    existing.write(vals)
                continue
            if manual_rates:
                continue
            Rate.create(
                {
                    "name": rec.name,
                    "currency_id": rec.currency_id.id,
                    "company_id": company.id,
                    **vals,
                }
            )
        self._recompute_open_documents_currency_rate()

    def _recompute_open_documents_currency_rate(self):
        currencies = self.mapped("currency_id")
        if not currencies:
            return
        Move = self.env["account.move"]
        moves = Move.search(
            [
                ("currency_id", "in", currencies.ids),
                ("state", "=", "draft"),
                (
                    "move_type",
                    "in",
                    (
                        "out_invoice",
                        "out_refund",
                        "out_receipt",
                        "in_invoice",
                        "in_refund",
                        "in_receipt",
                    ),
                ),
            ]
        )
        if moves:
            moves._compute_expected_currency_rate()
            moves._compute_invoice_currency_rate()
            moves.flush_recordset(
                ["expected_currency_rate", "invoice_currency_rate"]
            )
        if "purchase.order" not in self.env:
            return
        orders = self.env["purchase.order"].search(
            [
                ("currency_id", "in", currencies.ids),
                ("state", "in", ("draft", "sent", "to approve")),
            ]
        )
        if orders:
            orders._compute_currency_rate()
            orders.flush_recordset(["currency_rate"])

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        company = (
            self.env["res.company"].browse(self._context.get("company_id"))
            or self.env.company
        )
        index_name = company.currency_index_id.name or "Index"
        rate_name = (
            self.env["res.currency"].browse(self._context.get("active_id")).name
            or "Unit"
        )
        return key + (index_name, rate_name)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "list":
            company = (
                self.env["res.company"].browse(self._context.get("company_id"))
                or self.env.company
            )
            names = {
                "index_currency_name": company.currency_index_id.name or "Index",
                "rate_currency_name": (
                    self.env["res.currency"]
                    .browse(self._context.get("active_id"))
                    .name
                    or "Unit"
                ),
            }
            labels = [
                (
                    "rate",
                    _(
                        "%(index_currency_name)s per %(rate_currency_name)s",
                        **names,
                    ),
                ),
                (
                    "inverse_rate",
                    _(
                        "%(rate_currency_name)s per %(index_currency_name)s",
                        **names,
                    ),
                ),
            ]
            for name, label in labels:
                node = arch.find("./field[@name='%s']" % name)
                if node is not None:
                    node.set("string", label)
        return arch, view
