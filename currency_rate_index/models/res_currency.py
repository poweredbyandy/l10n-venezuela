# Copyright 2026 Anderson Armeya
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class ResCurrency(models.Model):
    _inherit = "res.currency"

    rate_index_ids = fields.One2many(
        "res.currency.rate.index",
        "currency_id",
        string="Index Rates",
    )
    is_index_currency = fields.Boolean(
        compute="_compute_is_index_currency",
    )

    @api.depends_context("company")
    def _compute_is_index_currency(self):
        index_currency = self.env.company.currency_index_id
        for currency in self:
            currency.is_index_currency = bool(
                index_currency and currency == index_currency
            )

    def _get_index_rate(self, company, date):
        self.ensure_one()
        index_currency = company.currency_index_id
        if not index_currency:
            return False
        if self == index_currency:
            return 1.0
        RateIndex = self.env["res.currency.rate.index"]
        rate = RateIndex.search(
            [
                ("currency_id", "=", self.id),
                ("name", "<=", date),
                ("company_id", "=", company.root_id.id),
            ],
            order="name desc",
            limit=1,
        )
        if not rate:
            rate = RateIndex.search(
                [
                    ("currency_id", "=", self.id),
                    ("name", "<=", date),
                    ("company_id", "=", False),
                ],
                order="name desc",
                limit=1,
            )
        return rate.rate if rate else False

    def _has_native_rate(self, company, date):
        self.ensure_one()
        return bool(
            self.env["res.currency.rate"].search(
                [
                    ("currency_id", "=", self.id),
                    ("name", "<=", date),
                    ("company_id", "in", (False, company.root_id.id)),
                ],
                limit=1,
            )
        )

    @api.model
    def _get_conversion_rate(self, from_currency, to_currency, company=None, date=None):
        if from_currency == to_currency:
            return 1
        if company == self.env.company.root_id:
            company = self.env.company
        else:
            company = company or self.env.company
        date = date or fields.Date.context_today(self)
        index_currency = company.currency_index_id
        company_currency = company.currency_id
        if not index_currency:
            return super()._get_conversion_rate(
                from_currency, to_currency, company=company, date=date
            )

        if (
            from_currency != company_currency
            and to_currency != company_currency
        ):
            from_index = from_currency._get_index_rate(company, date)
            to_index = to_currency._get_index_rate(company, date)
            if from_index and to_index:
                return from_index / to_index
            return super()._get_conversion_rate(
                from_currency, to_currency, company=company, date=date
            )

        if (
            to_currency == company_currency
            and from_currency not in (company_currency, index_currency)
        ):
            from_index = from_currency._get_index_rate(company, date)
            if from_index and not from_currency._has_native_rate(company, date):
                index_to_company = super()._get_conversion_rate(
                    index_currency, company_currency, company=company, date=date
                )
                return from_index * index_to_company

        if (
            from_currency == company_currency
            and to_currency not in (company_currency, index_currency)
        ):
            to_index = to_currency._get_index_rate(company, date)
            if to_index and not to_currency._has_native_rate(company, date):
                company_to_index = super()._get_conversion_rate(
                    company_currency, index_currency, company=company, date=date
                )
                return company_to_index / to_index

        return super()._get_conversion_rate(
            from_currency, to_currency, company=company, date=date
        )

    @api.model
    def _get_view_cache_key(self, view_id=None, view_type="form", **options):
        key = super()._get_view_cache_key(view_id, view_type, **options)
        company = (
            self.env["res.company"].browse(self._context.get("company_id"))
            or self.env.company
        )
        return key + (company.currency_index_id.name,)

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type == "form":
            company = (
                self.env["res.company"].browse(self._context.get("company_id"))
                or self.env.company
            )
            index_name = company.currency_index_id.name or "Index"
            for fname, label in (
                ("rate", _("%s per Unit", index_name)),
                ("inverse_rate", _("Unit per %s", index_name)),
            ):
                nodes = arch.xpath(
                    "//page[@name='rate_index']//list//field[@name='%s']" % fname
                )
                for node in nodes:
                    node.set("string", label)
        return arch, view
