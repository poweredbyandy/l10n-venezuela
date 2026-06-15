# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestProductTemplateL10nVe(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sale_tax = cls.company_data["default_tax_sale"]
        cls.purchase_tax = cls.company_data["default_tax_purchase"]
        cls.sale_tax_b = cls.env["account.tax"].create(
            {
                "name": "IVA Venta B VE Test",
                "amount": 8.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "company_id": cls.env.company.id,
            }
        )
        cls.purchase_tax_b = cls.env["account.tax"].create(
            {
                "name": "IVA Compra B VE Test",
                "amount": 5.0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": cls.env.company.id,
            }
        )

    def _create_product_vals(self, **extra):
        base = {
            "name": "Product VE tax test",
            "company_id": self.env.company.id,
            "list_price": 100.0,
            "standard_price": 50.0,
            "taxes_id": [(6, 0, [self.sale_tax.id])],
            "supplier_taxes_id": [(6, 0, [self.purchase_tax.id])],
        }
        base.update(extra)
        return base

    def test_ve_product_requires_one_sale_tax(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].with_context(
                l10n_ve_skip_auto_exent_taxes=True
            ).create(self._create_product_vals(taxes_id=[(6, 0, [])]))

    def test_ve_product_requires_one_purchase_tax(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].with_context(
                l10n_ve_skip_auto_exent_taxes=True
            ).create(self._create_product_vals(supplier_taxes_id=[(6, 0, [])]))

    def test_ve_product_rejects_multiple_sale_taxes(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create(
                self._create_product_vals(
                    taxes_id=[(6, 0, [self.sale_tax.id, self.sale_tax_b.id])]
                )
            )

    def test_ve_product_rejects_multiple_purchase_taxes(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create(
                self._create_product_vals(
                    supplier_taxes_id=[
                        (6, 0, [self.purchase_tax.id, self.purchase_tax_b.id])
                    ]
                )
            )

    def test_ve_product_one_each_ok(self):
        p = self.env["product.template"].create(self._create_product_vals())
        self.assertEqual(len(p.taxes_id), 1)
        self.assertEqual(len(p.supplier_taxes_id), 1)

    def test_ve_product_auto_exent_when_created_without_taxes(self):
        p = self.env["product.template"].create(
            {
                "name": "Producto sin impuestos en vals",
                "company_id": self.env.company.id,
                "list_price": 100.0,
                "standard_price": 50.0,
            }
        )
        self.assertEqual(len(p.taxes_id), 1)
        self.assertEqual(len(p.supplier_taxes_id), 1)
        self.assertEqual(p.taxes_id.amount, 0.0)
        self.assertEqual(p.supplier_taxes_id.amount, 0.0)

    def test_ve_product_coerces_non_positive_list_price(self):
        p = self.env["product.template"].create(
            self._create_product_vals(list_price=0.0, standard_price=0.0)
        )
        self.assertEqual(p.list_price, 1.0)

    def test_ve_product_coerces_zero_list_price_to_at_least_cost(self):
        p = self.env["product.template"].create(
            self._create_product_vals(list_price=0.0, standard_price=45.0)
        )
        self.assertEqual(p.list_price, 45.0)

    def test_ve_product_product_create_coerces_zero_list_price(self):
        tmpl = self.env["product.template"].with_context(
            l10n_ve_skip_auto_exent_taxes=True
        ).create(
            {
                "name": "Variant zero price VE",
                "type": "service",
                "company_id": self.env.company.id,
                "list_price": 0.0,
                "standard_price": 0.0,
                "taxes_id": [(6, 0, self.product_a.taxes_id.ids)],
                "supplier_taxes_id": [
                    (6, 0, self.product_a.product_tmpl_id.supplier_taxes_id.ids)
                ],
            }
        )
        p = tmpl.product_variant_id
        self.assertEqual(p.list_price, 1.0)

    def test_ve_product_allows_list_price_below_cost_when_not_enforced(self):
        p = self.env["product.template"].create(
            self._create_product_vals(list_price=40.0, standard_price=50.0)
        )
        self.assertEqual(p.list_price, 40.0)
        self.assertEqual(p.standard_price, 50.0)

    def test_ve_product_rejects_list_price_below_cost_when_enforced(self):
        self.env.company.l10n_ve_enforce_sale_price_ge_cost = True
        with self.assertRaises(ValidationError):
            self.env["product.template"].create(
                self._create_product_vals(list_price=40.0, standard_price=50.0)
            )

    def test_ve_product_allows_list_price_equal_to_cost(self):
        p = self.env["product.template"].create(
            self._create_product_vals(list_price=50.0, standard_price=50.0)
        )
        self.assertEqual(p.list_price, 50.0)

    def test_non_ve_fiscal_company_skips_tax_count_constraint(self):
        us = self.env.ref("base.us")
        company = self.env["res.company"].create(
            {
                "name": "US Co template test",
                "country_id": us.id,
            }
        )
        company.account_fiscal_country_id = us
        p = self.env["product.template"].create(
            {
                "name": "Sin impuestos US",
                "company_id": company.id,
                "list_price": 10.0,
                "taxes_id": [],
                "supplier_taxes_id": [],
            }
        )
        self.assertEqual(len(p.taxes_id), 0)

    def test_non_ve_fiscal_company_skips_price_constraint(self):
        us = self.env.ref("base.us")
        company = self.env["res.company"].create(
            {
                "name": "US Co price test",
                "country_id": us.id,
            }
        )
        company.account_fiscal_country_id = us
        p = self.env["product.template"].create(
            {
                "name": "Precio cero US",
                "company_id": company.id,
                "list_price": 0.0,
                "standard_price": 0.0,
                "taxes_id": [],
                "supplier_taxes_id": [],
            }
        )
        self.assertEqual(p.list_price, 0.0)
