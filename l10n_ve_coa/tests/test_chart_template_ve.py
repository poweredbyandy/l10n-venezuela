from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestL10nVeCoa(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chart_template = cls.env["account.chart.template"]

    def test_templates_belong_to_coa(self):
        mapping = self.chart_template._get_chart_template_mapping()
        for code in ("ve_seniat", "ve_seniat_basic", "ve_seniat_empty"):
            self.assertEqual(mapping[code]["module"], "l10n_ve_coa")
            self.assertEqual(mapping[code]["country_code"], "VE")

    def test_ve_seniat_template_data(self):
        data = self.chart_template._get_chart_template_data("ve_seniat")
        self.assertEqual(data["template_data"]["code_digits"], "7")
        self.assertEqual(
            data["template_data"]["property_account_receivable_id"],
            "account_account_1106001",
        )
        self.assertIn("account_account_1101001", data["account.account"])
        self.assertIn("account_group_1101", data["account.group"])
        company_vals = data["res.company"][self.env.company.id]
        self.assertEqual(
            company_vals["account_journal_early_pay_discount_loss_account_id"],
            "account_account_5102015",
        )
        self.assertEqual(
            company_vals["account_journal_early_pay_discount_gain_account_id"],
            "account_account_4102006",
        )
        self.assertEqual(
            company_vals["tax_calculation_rounding_method"], "round_globally"
        )

    def test_ve_seniat_basic_template_data(self):
        data = self.chart_template._get_chart_template_data("ve_seniat_basic")
        self.assertIn("account_account_1106001", data["account.account"])
        self.assertNotIn("account_account_1101001", data["account.account"])
        company_vals = data["res.company"][self.env.company.id]
        self.assertEqual(company_vals["account_fiscal_country_id"], "base.ve")
        self.assertEqual(company_vals["cash_account_code_prefix"], "1101")

    def test_ve_seniat_empty_has_no_accounts(self):
        data = self.chart_template._get_chart_template_data("ve_seniat_empty")
        self.assertNotIn("code_digits", data["template_data"])
        self.assertFalse(
            [
                xmlid
                for xmlid in data["account.account"]
                if xmlid.startswith("account_account_")
            ]
        )
        self.assertIn("tax1sale", data["account.tax"])
        self.assertIn("tax_group_iva_2", data["account.tax.group"])
        self.assertIn("fiscal_position_puerto_libre", data["account.fiscal.position"])
        company_vals = data["res.company"][self.env.company.id]
        self.assertEqual(company_vals["account_fiscal_country_id"], "base.ve")
        self.assertEqual(company_vals["account_sale_tax_id"], "tax1sale")
        self.assertNotIn("cash_account_code_prefix", company_vals)


@tagged("post_install", "-at_install")
class TestL10nVeCoaTaxes(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {"name": "VE Coa Company", "country_id": cls.env.ref("base.ve").id}
        )
        cls.env.user.company_ids |= cls.company
        cls.env = cls.env(
            context=dict(cls.env.context, allowed_company_ids=cls.company.ids)
        )
        cls.company = cls.company.with_env(cls.env)
        cls.env["account.chart.template"].try_loading(
            "ve_seniat", cls.company, install_demo=False
        )

    def _ref(self, xmlid):
        return self.env.ref(f"account.{self.company.id}_{xmlid}")

    def test_ve_seniat_loads_accounts(self):
        company = self.company
        self.assertEqual(company.chart_template, "ve_seniat")
        self.assertEqual(
            company.account_journal_early_pay_discount_loss_account_id.code,
            "5102015",
        )
        self.assertEqual(
            self._ref("account_account_1106001").account_type, "asset_receivable"
        )

    def test_company_default_taxes(self):
        company = self.company
        self.assertEqual(company.account_sale_tax_id, self._ref("tax1sale"))
        self.assertEqual(company.account_purchase_tax_id, self._ref("tax1purchase"))
        self.assertEqual(company.account_sale_tax_id.amount, 16.0)

    def test_tax_groups_keep_ve_fields(self):
        exempt = self._ref("tax_group_iva_0")
        general = self._ref("tax_group_iva_2")
        self.assertEqual(exempt.l10n_ve_aliquot_type, "exempt")
        self.assertEqual(general.l10n_ve_aliquot_type, "general")
        self.assertEqual(general.country_id, self.env.ref("base.ve"))

    def test_tax_repartition_uses_coa_accounts(self):
        tax_lines = self._ref("tax1sale").invoice_repartition_line_ids.filtered(
            lambda line: line.repartition_type == "tax"
        )
        self.assertEqual(tax_lines.account_id.code, "2102004")

    def test_fiscal_position_maps_taxes(self):
        position = self._ref("fiscal_position_puerto_libre")
        self.assertEqual(
            position.map_tax(self._ref("tax1sale")),
            self._ref("tax0sale"),
        )
