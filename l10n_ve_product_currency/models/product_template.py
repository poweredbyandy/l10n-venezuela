from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    force_currency_id = fields.Many2one(
        "res.currency",
        "Sales Price Currency",
        default=lambda self: self._default_force_currency_id(),
        help="Forced currency for the sales price. If empty, the company currency is used.",
    )
    force_cost_currency_id = fields.Many2one(
        "res.currency",
        "Forced Cost Currency",
        default=lambda self: self._default_force_cost_currency_id(),
        help="Forced currency for the cost. If empty, the company currency is used.",
    )
    company_currency_id = fields.Many2one(
        string="Company Currency",
        related="company_id.currency_id",
    )

    def _l10n_ve_param_currency(self, param_name):
        currency_id = (
            self.env["ir.config_parameter"].sudo().get_param(param_name)
        )
        try:
            return self.env["res.currency"].browse(int(currency_id)).exists()
        except (TypeError, ValueError):
            return self.env["res.currency"]

    def _l10n_ve_default_force_id(self, param_name):
        currency = self._l10n_ve_param_currency(param_name)
        if not currency or currency == self.env.company.currency_id:
            return False
        return currency.id

    def _default_force_currency_id(self):
        return self._l10n_ve_default_force_id(
            "l10n_ve_product_currency.default_force_currency_id"
        )

    def _default_force_cost_currency_id(self):
        return self._l10n_ve_default_force_id(
            "l10n_ve_product_currency.default_force_cost_currency_id"
        )

    def _l10n_ve_product_company(self):
        self.ensure_one()
        return self.company_id or self.env.company

    def _l10n_ve_force_value_for_dest(self, dest_currency):
        self.ensure_one()
        company = self._l10n_ve_product_company()
        if not dest_currency or dest_currency == company.currency_id:
            return False
        return dest_currency.id

    @api.depends("force_currency_id", "company_id", "company_id.currency_id")
    def _compute_currency_id(self):
        forced_products = self.filtered("force_currency_id")
        for rec in forced_products:
            rec.currency_id = rec.force_currency_id
        return super(ProductTemplate, self - forced_products)._compute_currency_id()

    @api.depends(
        "force_cost_currency_id",
        "company_id",
        "company_id.currency_id",
    )
    @api.depends_context("company")
    def _compute_cost_currency_id(self):
        forced_products = self.filtered("force_cost_currency_id")
        for rec in forced_products:
            rec.cost_currency_id = rec.force_cost_currency_id
        return super(
            ProductTemplate, self - forced_products
        )._compute_cost_currency_id()

    def write(self, vals):
        skip = self.env.context.get("skip_l10n_ve_currency_conversion")
        convert_sale = (
            not skip and "force_currency_id" in vals and "list_price" not in vals
        )
        convert_cost = (
            not skip
            and "force_cost_currency_id" in vals
            and "standard_price" not in vals
        )
        old_sale = {rec.id: rec.currency_id for rec in self} if convert_sale else {}
        old_cost = (
            {rec.id: rec.cost_currency_id for rec in self} if convert_cost else {}
        )
        res = super().write(vals)
        if convert_sale:
            self._l10n_ve_convert_sale_prices(old_sale)
        if convert_cost:
            self._l10n_ve_convert_cost_prices(old_cost)
        return res

    def _l10n_ve_convert_sale_prices(self, old_currencies):
        date = fields.Date.context_today(self)
        for rec in self:
            old_currency = old_currencies.get(rec.id)
            new_currency = rec.currency_id
            if not old_currency or not new_currency or old_currency == new_currency:
                continue
            company = rec._l10n_ve_product_company()
            rec.list_price = old_currency._convert(
                rec.list_price,
                new_currency,
                company,
                date,
            )

    def _l10n_ve_convert_cost_prices(self, old_currencies):
        date = fields.Date.context_today(self)
        companies = self.env["res.company"].search([])
        for rec in self:
            old_currency = old_currencies.get(rec.id)
            new_currency = rec.cost_currency_id
            if not old_currency or not new_currency or old_currency == new_currency:
                continue
            rec_companies = rec.company_id or companies
            variants = rec.product_variant_ids
            for product in variants:
                for company in rec_companies:
                    product_c = product.with_company(company).with_context(
                        disable_auto_svl=True,
                    )
                    product_c.standard_price = old_currency._convert(
                        product_c.standard_price,
                        new_currency,
                        company,
                        date,
                    )

    def _l10n_ve_migrate_currency(self, from_currency, to_currency, kind="sale"):
        if not from_currency or not to_currency or from_currency == to_currency:
            return self.browse()
        field = "currency_id" if kind == "sale" else "cost_currency_id"
        force_field = (
            "force_currency_id" if kind == "sale" else "force_cost_currency_id"
        )
        templates = self.filtered(lambda rec: rec[field] == from_currency)
        grouped = {}
        for rec in templates:
            value = rec._l10n_ve_force_value_for_dest(to_currency)
            grouped.setdefault(value, self.browse())
            grouped[value] |= rec
        for value, recs in grouped.items():
            recs.write({force_field: value})
        return templates
