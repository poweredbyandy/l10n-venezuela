# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.l10n_ve_reports.hooks import align_posted_tax_base_to_tax_totals

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

    def _assert_summary_nets_credit_notes(self, report, tax_label):
        options = self._generate_options(report, "2017-01-01", "2017-01-31")
        lines = report._get_lines(options)
        for section_key, is_total in (("general", False), ("total", True)):
            summary_line = self._get_summary_line(report, lines, section_key)
            self.assertAlmostEqual(
                self._get_column_value(summary_line, "tax_base_general_aliquot"),
                60.0,
            )
            self.assertAlmostEqual(
                self._get_column_value(summary_line, "amount_general_aliquot"),
                9.6,
            )
            self.assertTrue(summary_line["l10n_ve_summary"])
            self.assertEqual(
                summary_line["l10n_ve_summary_values"],
                {
                    "base": report.format_value(options, 60.0, "monetary"),
                    "tax": report.format_value(options, 9.6, "monetary"),
                    "tax_label": tax_label,
                    "is_total": is_total,
                },
            )
        return lines

    def test_sales_book_summary_subtracts_credit_notes(self):
        invoice = self._post_book_document(
            "out_invoice", 100.0, self.sale_general_tax, "00-1"
        )
        self._post_book_document(
            "out_refund", 40.0, self.sale_general_tax, "00-2", origin=invoice
        )
        lines = self._assert_summary_nets_credit_notes(
            self.env.ref("l10n_ve_reports.sales_book_report"), "Tax Debit"
        )
        self.assertFalse(self._book_move_line(lines, invoice).get("l10n_ve_summary"))

    def test_purchase_book_summary_subtracts_credit_notes(self):
        invoice = self._post_book_document(
            "in_invoice", 100.0, self.purchase_general_tax, "00-1"
        )
        self._post_book_document(
            "in_refund", 40.0, self.purchase_general_tax, "00-2", origin=invoice
        )
        lines = self._assert_summary_nets_credit_notes(
            self.env.ref("l10n_ve_reports.purchases_book_report"), "Tax Credit"
        )
        self.assertFalse(self._book_move_line(lines, invoice).get("l10n_ve_summary"))

    def test_fiscal_machine_book_summary_compact_values(self):
        report = self.env.ref("l10n_ve_reports.sales_book_fiscal_machine_report")
        options = self._generate_options(report, "2017-01-01", "2017-01-31")
        lines = report._get_lines(options)
        summary_lines = [line for line in lines if line.get("l10n_ve_summary_values")]
        self.assertEqual(len(summary_lines), 7)
        self.assertTrue(summary_lines[-1]["l10n_ve_summary_values"]["is_total"])
        self.assertEqual(
            summary_lines[-1]["l10n_ve_summary_values"]["tax_label"], "Tax Debit"
        )
        self.assertTrue(
            all(
                line.get("l10n_ve_summary")
                for line in lines
                if line.get("class") in ("resume_separator", "resume_title")
            )
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

    def _create_emitted_iva_retention(
        self, move, voucher_date, accounting_date, amount, number
    ):
        journal = self.company_data["default_journal_bank"]
        if move.is_purchase_document(include_receipts=True):
            payment_type = "outbound"
            partner_type = "supplier"
            method = journal.outbound_payment_method_line_ids[:1]
        else:
            payment_type = "inbound"
            partner_type = "customer"
            method = journal.inbound_payment_method_line_ids[:1]
        self.env["account.retention"].create(
            {
                "type_retention": "iva",
                "type": move.move_type,
                "partner_id": move.partner_id.id,
                "company_id": move.company_id.id,
                "date": voucher_date,
                "date_accounting": accounting_date,
                "state": "emitted",
                "number": number,
                "payment_ids": [
                    Command.create(
                        {
                            "amount": amount,
                            "payment_type": payment_type,
                            "partner_type": partner_type,
                            "partner_id": move.partner_id.id,
                            "journal_id": journal.id,
                            "payment_method_line_id": method.id,
                            "date": accounting_date,
                            "is_retention": True,
                        }
                    )
                ],
                "retention_line_ids": [
                    Command.create(
                        {
                            "name": "Retencion IVA",
                            "move_id": move.id,
                            "invoice_amount": move.amount_untaxed,
                            "invoice_total": move.amount_total,
                            "retention_amount": amount,
                            "iva_amount": amount,
                            "related_percentage_tax_base": 100.0,
                        }
                    )
                ],
            }
        )
        move.iva_voucher_number = number

    def _book_move_line(self, lines, move):
        names = {name for name in (move.name, move.ref) if name}
        return next(line for line in lines if line.get("name") in names)

    def test_sales_book_shows_retention_on_its_accounting_date(self):
        invoice = self._post_book_document(
            "out_invoice", 100.0, self.sale_general_tax, "00-RET"
        )
        self._create_emitted_iva_retention(
            invoice, "2017-02-10", "2017-02-10", 16.0, "20170200000099"
        )
        report = self.env.ref("l10n_ve_reports.sales_book_report")

        january_lines = report._get_lines(
            self._generate_options(report, "2017-01-01", "2017-01-31")
        )
        january_line = self._book_move_line(january_lines, invoice)
        self.assertAlmostEqual(
            self._get_column_value(january_line, "tax_base_general_aliquot"), 100.0
        )
        self.assertAlmostEqual(
            self._get_column_value(january_line, "iva_retained") or 0.0, 0.0
        )

        february_lines = report._get_lines(
            self._generate_options(report, "2017-02-01", "2017-02-28")
        )
        february_line = self._book_move_line(february_lines, invoice)
        self.assertEqual(
            self._get_column_value(february_line, "number_retention"),
            "20170200000099",
        )
        self.assertAlmostEqual(
            self._get_column_value(february_line, "iva_retained"), 16.0
        )
        self.assertAlmostEqual(
            self._get_column_value(february_line, "tax_base_general_aliquot") or 0.0,
            0.0,
        )
        self.assertAlmostEqual(
            self._get_column_value(february_line, "total_sales_iva") or 0.0, 0.0
        )
        summary = self._get_summary_line(report, february_lines, "general")
        self.assertAlmostEqual(
            self._get_column_value(summary, "tax_base_general_aliquot") or 0.0, 0.0
        )

    def test_purchase_book_shows_retention_on_voucher_date(self):
        bill = self._post_book_document(
            "in_invoice", 100.0, self.purchase_general_tax, "00-RET-P"
        )
        self._create_emitted_iva_retention(
            bill, "2017-02-10", "2017-02-10", 16.0, "20170200000098"
        )
        report = self.env.ref("l10n_ve_reports.purchases_book_report")
        february_lines = report._get_lines(
            self._generate_options(report, "2017-02-01", "2017-02-28")
        )
        february_line = self._book_move_line(february_lines, bill)
        self.assertEqual(
            self._get_column_value(february_line, "number_retention"),
            "20170200000098",
        )
        self.assertAlmostEqual(
            self._get_column_value(february_line, "iva_retained"), 16.0
        )
        self.assertAlmostEqual(
            self._get_column_value(february_line, "tax_base_general_aliquot") or 0.0,
            0.0,
        )

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

    def test_sales_book_general_base_follows_tax_lines(self):
        foreign = self.env.ref("base.EUR")
        foreign.active = True
        invoice_date = fields.Date.from_string("2017-01-15")
        self.env["res.currency.rate"].create(
            {
                "currency_id": foreign.id,
                "company_id": self.env.company.id,
                "name": invoice_date,
                "inverse_company_rate": 876.7976,
            }
        )
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_a.id,
                "invoice_date": invoice_date,
                "date": invoice_date,
                "currency_id": foreign.id,
                "l10n_ve_control_number": "00-FX",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Book line",
                            "quantity": 3.0,
                            "price_unit": 28.931271,
                            "tax_ids": [Command.set(self.sale_general_tax.ids)],
                        }
                    )
                ],
            }
        )
        move.action_post()
        tax_lines = move.line_ids.filtered("tax_line_id")
        values = self.env[
            "account.sales.book.report.handler.oca"
        ]._calculate_tax_values(move)
        self.assertAlmostEqual(
            values["base_general"],
            abs(sum(tax_lines.mapped("tax_base_amount"))),
            places=2,
        )
        self.assertAlmostEqual(
            values["amount_general"],
            abs(sum(tax_lines.mapped("balance"))),
            places=2,
        )

    def test_posted_tax_base_aligns_to_tax_totals(self):
        move = self._post_book_document(
            "out_invoice", 100.0, self.sale_general_tax, "00-ALIGN"
        )
        tax_line = move.line_ids.filtered("tax_line_id")[:1]
        self.assertTrue(tax_line)
        target = abs(
            next(
                tax_group.get("base_amount") or 0.0
                for subtotal in (move.tax_totals or {}).get("subtotals") or []
                for tax_group in subtotal.get("tax_groups") or []
                if tax_group.get("id") == self.general_tax_group.id
            )
        )
        self.env.cr.execute(
            """
            UPDATE account_move_line
               SET tax_base_amount = tax_base_amount + 0.04
             WHERE id = %s
            """,
            (tax_line.id,),
        )
        tax_line.invalidate_recordset(["tax_base_amount"])
        self.assertNotAlmostEqual(abs(tax_line.tax_base_amount), target, places=2)
        updated, _skipped = align_posted_tax_base_to_tax_totals(self.env, move)
        self.assertEqual(updated, 1)
        tax_line.invalidate_recordset(["tax_base_amount"])
        self.assertAlmostEqual(abs(tax_line.tax_base_amount), target, places=2)
        values = self.env[
            "account.sales.book.report.handler.oca"
        ]._calculate_tax_values(move)
        self.assertAlmostEqual(values["base_general"], target, places=2)
