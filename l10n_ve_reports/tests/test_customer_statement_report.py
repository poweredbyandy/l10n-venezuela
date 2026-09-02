# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from .common import TestAccountReportsCommon


@tagged("post_install", "-at_install")
class TestCustomerStatementReport(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("l10n_ve_reports.customer_statement_report")
        cls.init_invoice(
            "out_invoice",
            partner=cls.partner_a,
            invoice_date="2017-01-15",
            post=True,
            amounts=[100.0],
        )

    def _get_column_value(self, line, expression_label):
        for column in line.get("columns", []):
            if column.get("expression_label") == expression_label:
                return column.get("no_format")
        return None

    def _get_customer_statement_lines(self, display_currency=None):
        default_options = {
            "unfold_all": True,
            "currency_rate_date_type": "document",
        }
        if display_currency:
            default_options["display_currency_id"] = display_currency.id
        options = self._generate_options(
            self.report,
            "2017-01-01",
            "2017-12-31",
            default_options=default_options,
        )
        return self.report._get_lines(options), options

    def test_partner_section_total_matches_grand_total_in_display_currency(self):
        lines, _options = self._get_customer_statement_lines(
            display_currency=self.other_currency
        )
        partner_header = next(
            line for line in lines if line.get("name") == self.partner_a.name
        )
        partner_total = next(
            line
            for line in lines
            if line.get("name") == f"Total {self.partner_a.name}"
        )
        grand_total = next(
            line
            for line in lines
            if line.get("name") == "Total" and not line.get("parent_id")
        )

        for expression_label in ("amount", "balance"):
            header_value = self._get_column_value(partner_header, expression_label)
            section_value = self._get_column_value(partner_total, expression_label)
            grand_value = self._get_column_value(grand_total, expression_label)
            self.assertIsNotNone(header_value)
            self.assertAlmostEqual(section_value, header_value)
            self.assertAlmostEqual(grand_value, section_value)

    def test_partner_section_total_matches_grand_total_in_company_currency(self):
        lines, _options = self._get_customer_statement_lines()
        partner_total = next(
            line
            for line in lines
            if line.get("name") == f"Total {self.partner_a.name}"
        )
        grand_total = next(
            line
            for line in lines
            if line.get("name") == "Total" and not line.get("parent_id")
        )
        self.assertAlmostEqual(
            self._get_column_value(partner_total, "amount"),
            self._get_column_value(grand_total, "amount"),
        )
        self.assertAlmostEqual(
            self._get_column_value(partner_total, "balance"),
            self._get_column_value(grand_total, "balance"),
        )
