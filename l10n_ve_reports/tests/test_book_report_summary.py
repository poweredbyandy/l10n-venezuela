# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command
from odoo.tests import tagged

from .common import TestAccountReportsCommon


@tagged("post_install", "-at_install")
class TestBookReportSummary(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        venezuela = cls.env.ref("base.ve")
        company = cls.company_data["company"]
        company.account_fiscal_country_id = venezuela
        cls.general_tax_group = cls.env["account.tax.group"].create(
            {
                "name": "IVA General",
                "company_id": company.id,
                "country_id": venezuela.id,
                "l10n_ve_aliquot_type": "general",
            }
        )
        cls.sale_general_tax = cls._create_general_tax("sale", venezuela)
        cls.purchase_general_tax = cls._create_general_tax("purchase", venezuela)

    @classmethod
    def _create_general_tax(cls, type_tax_use, country):
        return cls.env["account.tax"].create(
            {
                "name": f"IVA 16% {type_tax_use}",
                "amount_type": "percent",
                "amount": 16.0,
                "type_tax_use": type_tax_use,
                "tax_group_id": cls.general_tax_group.id,
                "country_id": country.id,
                "company_id": cls.company_data["company"].id,
            }
        )

    def _post_book_document(self, move_type, amount, tax, control_number, origin=None):
        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": self.partner_a.id,
                "invoice_date": "2017-01-15",
                "date": "2017-01-15",
                "ref": control_number,
                "reversed_entry_id": origin.id if origin else False,
                "l10n_ve_control_number": control_number,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Book line",
                            "quantity": 1.0,
                            "price_unit": amount,
                            "tax_ids": [Command.set(tax.ids)],
                        }
                    )
                ],
            }
        )
        move.action_post()
        return move

    def _get_summary_line(self, report, lines, section_key):
        line_id = report._get_generic_line_id(
            None, None, markup=f"resume_{section_key}"
        )
        return next(line for line in lines if line["id"].endswith(line_id))

    def _get_column_value(self, line, expression_label):
        for column in line["columns"]:
            if column.get("expression_label") == expression_label:
                return column.get("no_format")
        return None

    def _assert_summary_nets_credit_notes(self, report):
        options = self._generate_options(report, "2017-01-01", "2017-01-31")
        lines = report._get_lines(options)
        for section_key in ("general", "total"):
            summary_line = self._get_summary_line(report, lines, section_key)
            self.assertAlmostEqual(
                self._get_column_value(summary_line, "tax_base_general_aliquot"),
                60.0,
            )
            self.assertAlmostEqual(
                self._get_column_value(summary_line, "amount_general_aliquot"),
                9.6,
            )

    def test_sales_book_summary_subtracts_credit_notes(self):
        invoice = self._post_book_document(
            "out_invoice", 100.0, self.sale_general_tax, "00-1"
        )
        self._post_book_document(
            "out_refund", 40.0, self.sale_general_tax, "00-2", origin=invoice
        )
        self._assert_summary_nets_credit_notes(
            self.env.ref("l10n_ve_reports.sales_book_report")
        )

    def test_purchase_book_summary_subtracts_credit_notes(self):
        invoice = self._post_book_document(
            "in_invoice", 100.0, self.purchase_general_tax, "00-1"
        )
        self._post_book_document(
            "in_refund", 40.0, self.purchase_general_tax, "00-2", origin=invoice
        )
        self._assert_summary_nets_credit_notes(
            self.env.ref("l10n_ve_reports.purchases_book_report")
        )

    def _create_ve_tax_group(self, name, **values):
        return self.env["account.tax.group"].create(
            {
                "name": name,
                "company_id": self.company_data["company"].id,
                "country_id": self.env.ref("base.ve").id,
                **values,
            }
        )

    def _create_ve_tax(self, group, type_tax_use, amount):
        return self.env["account.tax"].create(
            {
                "name": f"{group.name} {type_tax_use}",
                "amount_type": "percent",
                "amount": amount,
                "type_tax_use": type_tax_use,
                "tax_group_id": group.id,
                "country_id": self.env.ref("base.ve").id,
                "company_id": self.company_data["company"].id,
            }
        )

    def test_book_total_with_vat_is_the_document_total(self):
        exempt_group = self._create_ve_tax_group(
            "Exento", l10n_ve_aliquot_type="exempt"
        )
        for move_type, type_tax_use, handler in (
            ("out_invoice", "sale", "account.sales.book.report.handler.oca"),
            ("in_invoice", "purchase", "account.purchase.book.report.handler.oca"),
        ):
            with self.subTest(move_type=move_type):
                exempt_tax = self._create_ve_tax(exempt_group, type_tax_use, 0.0)
                move = self._post_book_document(move_type, 50.0, exempt_tax, "00-9")
                values = self.env[handler]._calculate_tax_values(move)
                self.assertAlmostEqual(values["total_exempt"], 50.0)
                self.assertAlmostEqual(values["total_taxed"], 50.0)

    def test_sales_book_ignores_groups_excluded_from_reports(self):
        excluded_group = self._create_ve_tax_group(
            "Fuera de libros", l10n_ve_exclude_from_reports=True
        )
        excluded_tax = self._create_ve_tax(excluded_group, "sale", 5.0)
        move = self._post_book_document("out_invoice", 100.0, excluded_tax, "00-8")
        values = self.env[
            "account.sales.book.report.handler.oca"
        ]._calculate_tax_values(move)
        self.assertAlmostEqual(values["total_exempt"], 0.0)
        self.assertAlmostEqual(values["base_general"], 0.0)
        self.assertAlmostEqual(values["amount_general"], 0.0)
