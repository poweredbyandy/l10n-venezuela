# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, _, api, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._l10n_ve_inject_default_taxes_in_vals(vals)
        products = super(
            ProductTemplate,
            self.with_context(l10n_ve_skip_product_tax_constraint=True),
        ).create(vals_list)
        products = products.with_env(self.env)
        products._l10n_ve_ensure_one_tax_per_company()
        products._l10n_ve_check_exactly_one_tax_per_use()
        return products

    def write(self, vals):
        if self.env.context.get("l10n_ve_skip_auto_exent_taxes"):
            return super().write(vals)
        if "taxes_id" not in vals and "supplier_taxes_id" not in vals:
            return super().write(vals)
        if len(self) > 1:
            for rec in self:
                rec.write(vals)
            return True
        vals = dict(vals)
        self._l10n_ve_merge_hidden_company_taxes_into_vals(vals)
        res = super(
            ProductTemplate,
            self.with_context(l10n_ve_skip_product_tax_constraint=True),
        ).write(vals)
        self._l10n_ve_ensure_one_tax_per_company()
        self._l10n_ve_check_exactly_one_tax_per_use()
        return res

    def _force_default_sale_tax(self, companies):
        return super(
            ProductTemplate,
            self.with_context(l10n_ve_skip_product_tax_constraint=True),
        )._force_default_sale_tax(companies)

    def _force_default_purchase_tax(self, companies):
        return super(
            ProductTemplate,
            self.with_context(l10n_ve_skip_product_tax_constraint=True),
        )._force_default_purchase_tax(companies)

    @api.model
    def _l10n_ve_vals_get_company(self, vals):
        company = vals.get("company_id")
        if not company:
            return self.env.company
        if isinstance(company, models.Model):
            return company
        return self.env["res.company"].browse(company)

    @api.model
    def _l10n_ve_m2m_normalize_commands(self, value):
        if value is False or value is None:
            return [Command.clear()]
        if isinstance(value, models.BaseModel):
            return [Command.set(value.ids)]
        if isinstance(value, tuple):
            return [Command.set(list(value))]
        if value and not isinstance(value[0], list | tuple):
            return [Command.set(list(value))]
        return value

    @api.model
    def _l10n_ve_m2m_commands_have_tax_ids(self, field_name, vals):
        if field_name not in vals:
            return False
        commands = self._l10n_ve_m2m_normalize_commands(vals[field_name])
        if any(command[0] == Command.CREATE for command in commands):
            return True
        return bool(self._l10n_ve_m2m_ids_from_commands(commands))

    @api.model
    def _l10n_ve_m2m_ids_from_commands(self, commands):
        ids = []
        for command in self._l10n_ve_m2m_normalize_commands(commands):
            operation = command[0]
            if operation == Command.SET:
                ids = list(command[2] or [])
            elif operation == Command.CLEAR:
                ids = []
            elif operation == Command.LINK and command[1] not in ids:
                ids.append(command[1])
            elif operation in (Command.DELETE, Command.UNLINK) and command[1] in ids:
                ids.remove(command[1])
        return ids

    def _l10n_ve_merge_hidden_company_taxes_into_vals(self, vals):
        self.ensure_one()
        allowed = set(self.env.companies.ids)
        for field_name in ("taxes_id", "supplier_taxes_id"):
            if field_name not in vals:
                continue
            commands = self._l10n_ve_m2m_normalize_commands(vals[field_name])
            if not any(
                command[0] in (Command.CLEAR, Command.SET) for command in commands
            ):
                continue
            hidden = self.sudo()[field_name].filtered(
                lambda tax: tax.company_id.id not in allowed
            )
            if not hidden:
                continue
            new_ids = self._l10n_ve_m2m_ids_from_commands(commands)
            vals[field_name] = [Command.set(list(dict.fromkeys(new_ids + hidden.ids)))]

    @api.model
    def _l10n_ve_get_company_sale_tax(self, company):
        tax = company.sudo().account_sale_tax_id
        if tax:
            return tax
        return self.env["account.tax.group"]._l10n_ve_get_exent_sale_tax(company)

    @api.model
    def _l10n_ve_get_company_purchase_tax(self, company):
        tax = company.sudo().account_purchase_tax_id
        if tax:
            return tax
        return self.env["account.tax.group"]._l10n_ve_get_exent_purchase_tax(company)

    @api.model
    def _l10n_ve_inject_default_taxes_in_vals(self, vals):
        if self.env.context.get("l10n_ve_skip_auto_exent_taxes"):
            return
        ve = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve:
            return
        company = self._l10n_ve_vals_get_company(vals)
        if company.account_fiscal_country_id != ve:
            return
        TaxGroup = self.env["account.tax.group"]
        if not TaxGroup._l10n_ve_get_report_tax_groups(company):
            return
        if not self._l10n_ve_m2m_commands_have_tax_ids("taxes_id", vals):
            sale_tax = self._l10n_ve_get_company_sale_tax(company)
            if sale_tax:
                vals["taxes_id"] = [Command.set(sale_tax.ids)]
        if not self._l10n_ve_m2m_commands_have_tax_ids("supplier_taxes_id", vals):
            purchase_tax = self._l10n_ve_get_company_purchase_tax(company)
            if purchase_tax:
                vals["supplier_taxes_id"] = [Command.set(purchase_tax.ids)]

    def _l10n_ve_ve_companies(self, companies):
        ve_country = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve_country:
            return self.env["res.company"]
        return companies.filtered(
            lambda company: company.account_fiscal_country_id == ve_country
        )

    def _l10n_ve_skip_product_tax_rules(self):
        self.ensure_one()
        if (
            hasattr(self, "_l10n_ve_is_sale_discount_template")
            and self._l10n_ve_is_sale_discount_template()
        ):
            return True
        if (
            hasattr(self, "_l10n_ve_is_loyalty_reward_discount_template")
            and self._l10n_ve_is_loyalty_reward_discount_template()
        ):
            return True
        return False

    def _l10n_ve_companies_for_tax_count(self):
        """Companies whose tax counts must be validated for this product."""
        self.ensure_one()
        if self.company_id:
            companies = self._l10n_ve_ve_companies(self.company_id)
        else:
            companies = self._l10n_ve_ve_companies(self.env.companies)
        TaxGroup = self.env["account.tax.group"].sudo()
        return companies.filtered(
            lambda company: TaxGroup._l10n_ve_get_report_tax_groups(company)
        )

    def _l10n_ve_taxes_for_company(self, taxes, company):
        return taxes._filter_taxes_by_company(company)

    def _l10n_ve_missing_company_taxes(self):
        self.ensure_one()
        sale_to_add = self.env["account.tax"]
        purchase_to_add = self.env["account.tax"]
        if self._l10n_ve_skip_product_tax_rules():
            return sale_to_add, purchase_to_add
        for company in self._l10n_ve_companies_for_tax_count():
            if not self._l10n_ve_taxes_for_company(self.taxes_id, company):
                tax = self._l10n_ve_get_company_sale_tax(company)
                if tax:
                    sale_to_add |= tax
            if not self._l10n_ve_taxes_for_company(self.supplier_taxes_id, company):
                tax = self._l10n_ve_get_company_purchase_tax(company)
                if tax:
                    purchase_to_add |= tax
        return sale_to_add, purchase_to_add

    def _l10n_ve_ensure_one_tax_per_company(self):
        if self.env.context.get("l10n_ve_skip_auto_exent_taxes"):
            return
        for tmpl in self:
            sale_to_add, purchase_to_add = tmpl._l10n_ve_missing_company_taxes()
            if not sale_to_add and not purchase_to_add:
                continue
            vals = {}
            if sale_to_add:
                vals["taxes_id"] = [Command.link(tax_id) for tax_id in sale_to_add.ids]
            if purchase_to_add:
                vals["supplier_taxes_id"] = [
                    Command.link(tax_id) for tax_id in purchase_to_add.ids
                ]
            tmpl.with_context(
                l10n_ve_skip_product_tax_constraint=True,
                l10n_ve_skip_auto_exent_taxes=True,
            ).write(vals)

    @api.constrains("taxes_id", "supplier_taxes_id")
    def _l10n_ve_check_exactly_one_tax_per_use(self):
        """Exige exactamente un impuesto de venta y uno de compra por compañía VE.

        Notes
        -----
        Art. 13 num. 9-11 PA SNAT/2011/0071: alícuota aplicable por operación.
        En multi-compañía un producto compartido puede tener un impuesto por
        compañía; el conteo se hace por compañía, no sobre el total.
        """

        if self.env.context.get("install_mode") or self.env.context.get(
            "l10n_ve_skip_product_tax_constraint"
        ):
            return
        for tmpl in self:
            if tmpl._l10n_ve_skip_product_tax_rules():
                continue
            for company in tmpl._l10n_ve_companies_for_tax_count():
                n_sale = len(tmpl._l10n_ve_taxes_for_company(tmpl.taxes_id, company))
                if n_sale != 1:
                    raise ValidationError(
                        _(
                            'El producto "%(name)s" debe tener exactamente un '
                            "impuesto de ventas en la compañía “%(company)s” "
                            "(tiene %(n)d)."
                        )
                        % {
                            "name": tmpl.display_name,
                            "company": company.display_name,
                            "n": n_sale,
                        }
                    )
                n_purchase = len(
                    tmpl._l10n_ve_taxes_for_company(tmpl.supplier_taxes_id, company)
                )
                if n_purchase != 1:
                    raise ValidationError(
                        _(
                            'El producto "%(name)s" debe tener exactamente un '
                            "impuesto de compras en la compañía “%(company)s” "
                            "(tiene %(n)d)."
                        )
                        % {
                            "name": tmpl.display_name,
                            "company": company.display_name,
                            "n": n_purchase,
                        }
                    )
