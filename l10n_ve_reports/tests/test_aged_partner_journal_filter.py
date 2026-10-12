# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.tests import tagged

from .common import TestAccountReportsCommon


@tagged("post_install", "-at_install")
class TestAgedPartnerJournalFilter(TestAccountReportsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.receivable_report = cls.env.ref("l10n_ve_reports.aged_receivable_report")
        cls.payable_report = cls.env.ref("l10n_ve_reports.aged_payable_report")
        cls.report_date = "2025-03-10"
        cls.misc_journal = cls.company_data["default_journal_misc"]

    @classmethod
    def _create_entry(cls, journal, account, debit, credit):
        move = cls.env["account.move"].create(
            {
                "move_type": "entry",
                "date": fields.Date.from_string(cls.report_date),
                "journal_id": journal.id,
                "line_ids": [
                    Command.create(
                        {
                            "debit": debit,
                            "credit": credit,
                            "account_id": account.id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                    Command.create(
                        {
                            "debit": credit,
                            "credit": debit,
                            "account_id": cls.company_data[
                                "default_account_revenue"
                            ].id,
                            "partner_id": cls.partner_a.id,
                        }
                    ),
                ],
            }
        )
        move.action_post()
        return move.line_ids.filtered(lambda line: line.account_id == account)

    def _report_aml_ids(self, report, journals=None):
        default_options = {"unfold_all": True}
        if journals is not None:
            default_options["journals"] = [
                {"id": journal.id, "model": "account.journal", "selected": True}
                for journal in journals
            ]
        options = self._generate_options(
            report,
            self.report_date,
            self.report_date,
            default_options=default_options,
        )
        aml_ids = set()
        for line in report._get_lines(options):
            model, record_id = report._get_model_info_from_id(line["id"])
            if model == "account.move.line":
                aml_ids.add(record_id)
        return options, aml_ids

    def _assert_journal_filter(self, report, document_journal, account, debit, credit):
        document_line = self._create_entry(document_journal, account, debit, credit)
        misc_line = self._create_entry(self.misc_journal, account, debit, credit)

        options, all_aml_ids = self._report_aml_ids(report)
        self.assertIn("journals", options)
        self.assertTrue({document_line.id, misc_line.id} <= all_aml_ids)

        _options, filtered_aml_ids = self._report_aml_ids(
            report, journals=document_journal
        )
        self.assertIn(document_line.id, filtered_aml_ids)
        self.assertNotIn(misc_line.id, filtered_aml_ids)

    def test_receivable_filters_by_journal(self):
        self._assert_journal_filter(
            self.receivable_report,
            self.company_data["default_journal_sale"],
            self.company_data["default_account_receivable"],
            100.0,
            0.0,
        )

    def test_payable_filters_by_journal(self):
        self._assert_journal_filter(
            self.payable_report,
            self.company_data["default_journal_purchase"],
            self.company_data["default_account_payable"],
            0.0,
            100.0,
        )
