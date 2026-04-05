# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestChartTemplateVe(L10nVeSeniatCommon):
    def test_ve_seniat_template_data(self):
        tpl = self.env["account.chart.template"]
        funcs = tpl._template_register["ve_seniat"]["template_data"]
        self.assertTrue(funcs)
        data = funcs[0](tpl)
        self.assertEqual(data.get("code_digits"), "7")

    def test_ve_seniat_empty_res_company_template(self):
        tpl = self.env["account.chart.template"]
        funcs = tpl._template_register["ve_seniat_empty"]["res.company"]
        self.assertTrue(funcs)
        data = funcs[0](tpl)
        self.assertIn(self.env.company.id, data)
        row = data[self.env.company.id]
        self.assertEqual(row["account_fiscal_country_id"], "base.ve")
