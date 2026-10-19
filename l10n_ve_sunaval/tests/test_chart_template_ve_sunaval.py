from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestChartTemplateVeSunaval(L10nVeSeniatCommon):
    @classmethod
    def _use_chart_template(cls, company, chart_template_ref=None):
        return super()._use_chart_template(company, "ve_sunaval")

    def _account(self, code):
        return self.env["account.account"].search(
            [
                *self.env["account.account"]._check_company_domain(self.company),
                ("code", "=", code),
            ]
        )

    def test_chart_is_loaded(self):
        self.assertEqual(self.company.chart_template, "ve_sunaval")
        self.assertEqual(self.company.account_fiscal_country_id.code, "VE")
        Account = self.env["account.account"]
        self.assertGreaterEqual(
            Account.search_count(Account._check_company_domain(self.company)), 1318
        )

    def test_accounts_used_by_financing_entries(self):
        expected = {
            "131830100001": "asset_current",
            "131830102001": "asset_current",
            "131830103001": "asset_current",
            "131830104001": "asset_receivable",
            "139810100001": "asset_current",
            "142050101011": "asset_current",
            "144860100001": "asset_receivable",
            "27299010000101": "liability_payable",
            "272150100001": "liability_payable",
            "27214010100101": "liability_current",
            "27281010100102": "liability_current",
            "421810101001": "expense",
            "441160100001": "expense",
            "51380010103": "income",
            "51380010303": "income",
            "531880101011": "income_other",
            "532980107": "income_other",
            "11301010101101": "asset_cash",
            "11102010000101": "asset_cash",
        }
        for code, account_type in expected.items():
            account = self._account(code)
            self.assertTrue(account, code)
            self.assertEqual(account.account_type, account_type, code)
        self.assertTrue(self._account("27214010100101").reconcile)
        installments = self._account("131830104001")
        self.assertTrue(installments.reconcile)
        self.assertEqual(installments.group_id.code_prefix_start, "1318301")

    def test_parent_codes_are_groups(self):
        account = self._account("131830100001")
        self.assertEqual(account.group_id.code_prefix_start, "1318301")
        self.assertFalse(self._account("1318301"))
        prefixes = []
        group = account.group_id
        while group:
            prefixes.append(group.code_prefix_start)
            group = group.parent_id
        self.assertEqual(prefixes, ["1318301", "13183", "1318", "131", "13", "1"])

    def test_company_defaults(self):
        company = self.company
        self.assertEqual(company.income_currency_exchange_account_id.code, "532980107")
        self.assertEqual(company.expense_currency_exchange_account_id.code, "432980107")
        self.assertEqual(company.account_journal_suspense_account_id.code, "186020100001")
        self.assertEqual(company.transfer_account_id.code, "186030100001")
        bank = self.company_data["default_journal_bank"]
        self.assertEqual(bank.default_account_id.code, "11301010101101")
        self.assertEqual(
            self.company_data["default_journal_cash"].default_account_id.code,
            "111010100001",
        )

    def test_sale_tax_posts_to_vat_payable(self):
        tax = self.company.account_sale_tax_id
        self.assertEqual(tax.amount, 16.0)
        accounts = tax.invoice_repartition_line_ids.filtered(
            lambda line: line.repartition_type == "tax"
        ).account_id
        self.assertEqual(accounts.code, "27281010100102")
        purchase = self.company.account_purchase_tax_id.invoice_repartition_line_ids
        self.assertEqual(
            purchase.filtered(lambda line: line.repartition_type == "tax").account_id.code,
            "27281010100101",
        )

    def test_receivable_and_payable_defaults(self):
        partner = self.partner_a.with_company(self.company)
        self.assertEqual(partner.property_account_receivable_id.code, "144860100001")
        self.assertEqual(partner.property_account_payable_id.code, "27201010000101")
