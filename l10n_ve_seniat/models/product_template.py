# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_ve_sale_taxes_readonly = fields.Boolean(
        compute="_compute_l10n_ve_sale_taxes_readonly",
    )

    @api.depends("product_variant_ids")
    def _compute_l10n_ve_sale_taxes_readonly(self):
        locked = self.env["product.template"]._l10n_ve_locked_sale_tax_template_id_set(
            self
        )
        for tmpl in self:
            tmpl.l10n_ve_sale_taxes_readonly = tmpl.id in locked

    @api.model
    def _l10n_ve_locked_sale_tax_template_id_set(self, templates):
        ve = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve or not templates:
            return set()
        candidates = templates.filtered(
            lambda t: (t.company_id or self.env.company).account_fiscal_country_id == ve
        )
        if not candidates:
            return set()
        variant_ids = candidates.mapped("product_variant_ids").ids
        if not variant_ids:
            return set()
        self.env.cr.execute(
            """
            SELECT DISTINCT pp.product_tmpl_id
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN product_product pp ON pp.id = aml.product_id
            WHERE aml.product_id = ANY(%s)
              AND COALESCE(aml.display_type, '') NOT IN ('line_section', 'line_note')
              AND am.state = 'posted'
              AND am.move_type IN ('out_invoice', 'out_refund')
            """,
            (variant_ids,),
        )
        invoiced = {row[0] for row in self.env.cr.fetchall()}
        return invoiced & set(candidates.ids)

    def _l10n_ve_user_can_override_sale_tax_lock(self):
        return self.env.user.has_group(
            "l10n_ve_seniat.group_l10n_ve_override_locked_master_data"
        )

    def write(self, vals):
        if "taxes_id" in vals and not self._l10n_ve_user_can_override_sale_tax_lock():
            locked = self.env[
                "product.template"
            ]._l10n_ve_locked_sale_tax_template_id_set(self)
            if set(self.ids) & locked:
                raise ValidationError(
                    _(
                        "No puede modificar el impuesto de ventas de un producto que "
                        "ya figura en facturas de cliente o notas de crédito "
                        "confirmadas."
                    )
                )
        vals = dict(vals)
        if "list_price" in vals:
            ve_country = self.env.ref("base.ve", raise_if_not_found=False)
            if ve_country:
                ve_templates = self.filtered(
                    lambda t: (
                        t.company_id or self.env.company
                    ).account_fiscal_country_id
                    == ve_country
                )
                if ve_templates:
                    self._l10n_ve_normalize_list_price_in_vals(
                        vals, templates=ve_templates
                    )
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._l10n_ve_normalize_list_price_in_vals(vals)
            self._l10n_ve_inject_default_exent_taxes_in_vals(vals)
        return super().create(vals_list)

    @api.model
    def _l10n_ve_vals_get_company(self, vals):
        if "company_id" not in vals or vals["company_id"] is False:
            return self.env.company
        cid = vals["company_id"]
        if isinstance(cid, int):
            return self.env["res.company"].browse(cid)
        if isinstance(cid, models.Model):
            return cid
        if isinstance(cid, list | tuple) and len(cid) >= 2:
            if cid[0] == 4:
                return self.env["res.company"].browse(cid[1])
            if cid[0] == 1 and len(cid) >= 2:
                return self.env["res.company"].browse(cid[1])
        return self.env.company

    @api.model
    def _l10n_ve_m2m_commands_have_tax_ids(self, field_name, vals):
        if field_name not in vals:
            return False
        cmds = vals[field_name]
        if not cmds:
            return False
        for c in cmds:
            if c[0] == 6 and c[2]:
                return True
            if c[0] == 4:
                return True
            if c[0] == 3:
                return True
            if c[0] == 0:
                return True
        return False

    @api.model
    def _l10n_ve_get_exent_sale_tax(self, company):
        tax = company.exent_aliquot_sale
        if tax and float_compare(tax.amount, 0.0, precision_digits=4) == 0:
            return tax
        return self.env["account.tax"].search(
            [
                ("company_id", "parent_of", company.id),
                ("type_tax_use", "=", "sale"),
                ("amount", "=", 0.0),
            ],
            limit=1,
        )

    @api.model
    def _l10n_ve_get_exent_purchase_tax(self, company):
        tax = company.exent_aliquot_purchase
        if tax and float_compare(tax.amount, 0.0, precision_digits=4) == 0:
            return tax
        return self.env["account.tax"].search(
            [
                ("company_id", "parent_of", company.id),
                ("type_tax_use", "=", "purchase"),
                ("amount", "=", 0.0),
            ],
            limit=1,
        )

    @api.model
    def _l10n_ve_normalize_list_price_in_vals(self, vals, templates=None):
        ve_country = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve_country:
            return
        prec = self.env["decimal.precision"].precision_get("Product Price")

        if templates is not None:
            costs = [float(c or 0.0) for c in templates.mapped("standard_price")]
            if "standard_price" in vals:
                costs.append(float(vals.get("standard_price") or 0.0))
            cost_max = max(costs) if costs else 0.0
            if (
                "list_price" in vals
                and float_compare(vals["list_price"], 0.0, precision_digits=prec) <= 0
            ):
                vals["list_price"] = max(1.0, cost_max)
            return

        company = self._l10n_ve_vals_get_company(vals)
        if company.account_fiscal_country_id != ve_country:
            return
        cost = float(vals.get("standard_price", 0.0) or 0.0)
        if (
            "list_price" in vals
            and float_compare(vals["list_price"], 0.0, precision_digits=prec) <= 0
        ):
            vals["list_price"] = max(1.0, cost)

    @api.model
    def _l10n_ve_inject_default_exent_taxes_in_vals(self, vals):
        if self.env.context.get("l10n_ve_skip_auto_exent_taxes"):
            return
        ve = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve:
            return
        company = self._l10n_ve_vals_get_company(vals)
        if company.account_fiscal_country_id != ve:
            return
        if not hasattr(company, "exent_aliquot_sale"):
            return
        if not self._l10n_ve_m2m_commands_have_tax_ids("taxes_id", vals):
            sale_tax = self._l10n_ve_get_exent_sale_tax(company)
            if sale_tax:
                vals["taxes_id"] = [(6, 0, [sale_tax.id])]
        if not self._l10n_ve_m2m_commands_have_tax_ids("supplier_taxes_id", vals):
            purchase_tax = self._l10n_ve_get_exent_purchase_tax(company)
            if purchase_tax:
                vals["supplier_taxes_id"] = [(6, 0, [purchase_tax.id])]

    def _l10n_ve_is_sale_discount_template(self):
        self.ensure_one()
        Company = self.env["res.company"]
        if "sale_discount_product_id" not in Company._fields:
            return False
        ve = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve:
            return False
        discount_products = Company.search(
            [("account_fiscal_country_id", "=", ve.id)]
        ).mapped("sale_discount_product_id")
        if not discount_products:
            return False
        return bool(self.product_variant_ids & discount_products)

    def _l10n_ve_check_sale_price_vs_cost(self):
        ve_country = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve_country:
            return
        prec = self.env["decimal.precision"].precision_get("Product Price")
        for tmpl in self:
            if tmpl._l10n_ve_is_sale_discount_template():
                continue
            company = tmpl.company_id or self.env.company
            if company.account_fiscal_country_id != ve_country:
                continue
            enforce_ge_cost = company.l10n_ve_enforce_sale_price_ge_cost
            for variant in tmpl.product_variant_ids:
                lst = variant.lst_price
                cost = variant.standard_price
                if float_compare(lst, 0.0, precision_digits=prec) <= 0:
                    raise ValidationError(
                        _(
                            'El precio de venta del producto "%(name)s" debe ser '
                            "mayor que cero (variante: %(variant)s)."
                        )
                        % {
                            "name": tmpl.display_name,
                            "variant": variant.display_name,
                        }
                    )
                if (
                    enforce_ge_cost
                    and float_compare(lst, cost, precision_digits=prec) < 0
                ):
                    raise ValidationError(
                        _(
                            'El precio de venta del producto "%(name)s" no puede ser '
                            "inferior al coste (variante: %(variant)s)."
                        )
                        % {
                            "name": tmpl.display_name,
                            "variant": variant.display_name,
                        }
                    )

    @api.constrains("list_price", "standard_price")
    def _l10n_ve_check_list_price_and_cost(self):
        self._l10n_ve_check_sale_price_vs_cost()

    @api.constrains("taxes_id", "supplier_taxes_id")
    def _l10n_ve_check_exactly_one_tax_per_use(self):
        if self.env.context.get("install_mode") or self.env.context.get(
            "l10n_ve_skip_product_tax_constraint"
        ):
            return
        ve_country = self.env.ref("base.ve", raise_if_not_found=False)
        if not ve_country:
            return
        for tmpl in self:
            if tmpl._l10n_ve_is_sale_discount_template():
                continue
            company = tmpl.company_id or self.env.company
            if company.account_fiscal_country_id != ve_country:
                continue
            n_sale = len(tmpl.taxes_id)
            if n_sale != 1:
                raise ValidationError(
                    _(
                        'El producto "%(name)s" debe tener exactamente un impuesto de '
                        "ventas en compañías venezolanas (tiene %(n)d)."
                    )
                    % {"name": tmpl.display_name, "n": n_sale}
                )
            n_purchase = len(tmpl.supplier_taxes_id)
            if n_purchase != 1:
                raise ValidationError(
                    _(
                        'El producto "%(name)s" debe tener exactamente un impuesto de '
                        "compras en compañías venezolanas (tiene %(n)d)."
                    )
                    % {"name": tmpl.display_name, "n": n_purchase}
                )


class ProductProduct(models.Model):
    _inherit = "product.product"

    l10n_ve_sale_taxes_readonly = fields.Boolean(
        related="product_tmpl_id.l10n_ve_sale_taxes_readonly",
    )

    @api.model_create_multi
    def create(self, vals_list):
        Template = self.env["product.template"]
        for vals in vals_list:
            Template._l10n_ve_normalize_list_price_in_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if "list_price" in vals:
            ve_country = self.env.ref("base.ve", raise_if_not_found=False)
            if ve_country:
                ve_products = self.filtered(
                    lambda p: (
                        p.product_tmpl_id.company_id or self.env.company
                    ).account_fiscal_country_id
                    == ve_country
                )
                if ve_products:
                    self.env["product.template"]._l10n_ve_normalize_list_price_in_vals(
                        vals, templates=ve_products.product_tmpl_id
                    )
        return super().write(vals)
