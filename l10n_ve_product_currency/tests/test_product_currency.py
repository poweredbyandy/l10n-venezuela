from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestL10nVeProductCurrency(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_currency = cls.env.company.currency_id
        cls.other_currency = cls.env.ref("base.EUR")
        if cls.other_currency == cls.company_currency:
            cls.other_currency = cls.env.ref("base.USD")
        cls.other_currency.active = True
        cls.env["res.currency.rate"].search(
            [
                ("currency_id", "=", cls.other_currency.id),
                ("company_id", "=", cls.env.company.id),
            ]
        ).unlink()
        cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": cls.other_currency.id,
                "rate": 2.0,
                "company_id": cls.env.company.id,
            }
        )

    def _expected_amount(self, amount, from_currency, to_currency):
        return from_currency._convert(
            amount,
            to_currency,
            self.env.company,
            fields.Date.today(),
        )

    def test_sale_and_cost_currencies_are_independent(self):
        product = self.env["product.template"].create(
            {
                "name": "Independent currencies",
                "list_price": 100.0,
                "standard_price": 40.0,
                "force_currency_id": self.other_currency.id,
                "force_cost_currency_id": False,
            }
        )
        self.assertEqual(product.currency_id, self.other_currency)
        self.assertEqual(product.cost_currency_id, self.company_currency)

        product.write({"force_cost_currency_id": self.other_currency.id})
        self.assertEqual(product.currency_id, self.other_currency)
        self.assertEqual(product.cost_currency_id, self.other_currency)

        product.write({"force_currency_id": False})
        self.assertEqual(product.currency_id, self.company_currency)
        self.assertEqual(product.cost_currency_id, self.other_currency)

    def test_changing_sale_currency_converts_list_price_not_cost(self):
        product = self.env["product.template"].create(
            {
                "name": "Sale conversion",
                "list_price": 100.0,
                "standard_price": 40.0,
                "force_currency_id": self.company_currency.id,
                "force_cost_currency_id": self.company_currency.id,
            }
        )
        expected_sale = self._expected_amount(
            100.0,
            self.company_currency,
            self.other_currency,
        )
        product.write({"force_currency_id": self.other_currency.id})
        self.assertAlmostEqual(product.list_price, expected_sale, places=4)
        self.assertNotAlmostEqual(expected_sale, 100.0)
        self.assertAlmostEqual(product.standard_price, 40.0, places=4)
        self.assertEqual(product.currency_id, self.other_currency)
        self.assertEqual(product.cost_currency_id, self.company_currency)

    def test_changing_cost_currency_converts_standard_price_not_sale(self):
        product = self.env["product.template"].create(
            {
                "name": "Cost conversion",
                "list_price": 100.0,
                "standard_price": 40.0,
                "force_currency_id": self.company_currency.id,
                "force_cost_currency_id": self.company_currency.id,
            }
        )
        expected_cost = self._expected_amount(
            40.0,
            self.company_currency,
            self.other_currency,
        )
        product.write({"force_cost_currency_id": self.other_currency.id})
        self.assertAlmostEqual(product.standard_price, expected_cost, places=4)
        self.assertNotAlmostEqual(expected_cost, 40.0)
        self.assertAlmostEqual(product.list_price, 100.0, places=4)
        self.assertEqual(product.cost_currency_id, self.other_currency)
        self.assertEqual(product.currency_id, self.company_currency)

    def test_wizard_migrates_sale_and_keeps_cost_currency(self):
        product = self.env["product.template"].create(
            {
                "name": "Wizard migrate",
                "list_price": 100.0,
                "standard_price": 40.0,
                "force_currency_id": self.company_currency.id,
                "force_cost_currency_id": self.company_currency.id,
            }
        )
        expected_sale = self._expected_amount(
            100.0,
            self.company_currency,
            self.other_currency,
        )
        wizard = self.env["l10n.ve.product.currency.migrate.wizard"].create(
            {
                "migrate_sale": True,
                "migrate_cost": False,
                "sale_from_currency_id": self.company_currency.id,
                "sale_to_currency_id": self.other_currency.id,
            }
        )
        wizard.action_migrate()
        self.assertEqual(product.currency_id, self.other_currency)
        self.assertEqual(product.cost_currency_id, self.company_currency)
        self.assertAlmostEqual(product.list_price, expected_sale, places=4)
        self.assertAlmostEqual(product.standard_price, 40.0, places=4)

    def test_defaults_from_config_parameters(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(
            "l10n_ve_product_currency.default_force_currency_id",
            str(self.other_currency.id),
        )
        icp.set_param(
            "l10n_ve_product_currency.default_force_cost_currency_id",
            False,
        )
        product = self.env["product.template"].create(
            {
                "name": "Default currencies",
            }
        )
        self.assertEqual(product.force_currency_id, self.other_currency)
        self.assertEqual(product.currency_id, self.other_currency)
        self.assertFalse(product.force_cost_currency_id)
        self.assertEqual(product.cost_currency_id, self.company_currency)
