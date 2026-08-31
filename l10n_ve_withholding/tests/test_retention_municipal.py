from odoo import Command, fields
from odoo.exceptions import MissingError, UserError
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestRetentionMunicipal(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_date = fields.Date.from_string("2026-03-15")
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Proveedor municipal",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J998877665",
                "supplier_rank": 1,
            }
        )
        cls.branch = cls.env["economic.branch"].sudo().create(
            {
                "name": "RAMA MUNICIPAL TEST",
                "status": "active",
            }
        )
        municipality = cls.env["res.country.municipality"].search(
            [("country_id", "=", cls.env.ref("base.ve").id)],
            limit=1,
        )
        if not municipality:
            state = cls.env["res.country.state"].search(
                [("country_id", "=", cls.env.ref("base.ve").id)],
                limit=1,
            )
            municipality = cls.env["res.country.municipality"].sudo().create(
                {
                    "name": "MUNICIPIO TEST",
                    "code": "MUN-TEST-WH",
                    "country_id": cls.env.ref("base.ve").id,
                    "state_id": [Command.set(state.ids)],
                }
            )
        cls.economic_activity = cls.env["economic.activity"].sudo().create(
            {
                "name": "ACT-MUN-TEST",
                "municipality_id": municipality.id,
                "branch_id": cls.branch.id,
                "aliquot": 5.0,
                "description": "Actividad municipal de prueba",
                "minimum_monthly": 0.0,
                "minimum_annual": 0.0,
            }
        )
        cls.supplier.economic_activity_id = cls.economic_activity
        journal = cls.env.company.municipal_supplier_retention_journal_id
        if not journal:
            journal = cls.company_data["default_journal_bank"]
            cls.env.company.municipal_supplier_retention_journal_id = journal
        cls.municipal_journal = journal
        cls.env.company.tax_authorities_name = "Alcaldia Test"

    def _create_vendor_bill(self, price_unit=1000.0, post=False):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "invoice_date": self.test_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Compra municipal",
                            "quantity": 1.0,
                            "price_unit": price_unit,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [self.company_data["default_tax_purchase"].id]
                                )
                            ],
                        }
                    )
                ],
            }
        )
        if post:
            bill.action_post()
        return bill

    def _add_municipal_line(self, bill, invoice_amount=None):
        invoice_amount = (
            invoice_amount
            if invoice_amount is not None
            else bill._l10n_ve_sum_lines_company_base(
                bill.invoice_line_ids.filtered(
                    lambda line: line.display_type == "product"
                )
            )
        )
        invoice_total = abs(bill.amount_total_signed)
        bill.write(
            {
                "retention_municipal_line_ids": [
                    Command.create(
                        {
                            "name": "Municipal Retention",
                            "economic_activity_id": self.economic_activity.id,
                            "aliquot": self.economic_activity.aliquot,
                            "invoice_amount": invoice_amount,
                            "invoice_total": invoice_total,
                            "retention_amount": invoice_amount
                            * self.economic_activity.aliquot
                            / 100,
                        }
                    )
                ]
            }
        )
        return bill.retention_municipal_line_ids

    def test_municipal_onchange_uses_company_currency(self):
        bill = self._create_vendor_bill(price_unit=200.0)
        line = self.env["account.retention.line"].new(
            {
                "move_id": bill.id,
                "economic_activity_id": self.economic_activity.id,
            }
        )
        line.onchange_economic_activity_id()
        line.onchange_municipal_invoice_amount()
        self.assertEqual(line.aliquot, 5.0)
        self.assertAlmostEqual(line.invoice_amount, 200.0, places=2)
        self.assertAlmostEqual(line.retention_amount, 10.0, places=2)

    def test_municipal_base_includes_exempt_lines(self):
        tax_exempt = self.env["account.tax"].search(
            [
                ("company_id", "=", self.env.company.id),
                ("type_tax_use", "=", "purchase"),
                ("amount", "=", 0),
            ],
            limit=1,
        )
        if not tax_exempt:
            tax_exempt = self.env["account.tax"].create(
                {
                    "name": "IVA Exento municipal",
                    "amount": 0.0,
                    "amount_type": "percent",
                    "type_tax_use": "purchase",
                    "company_id": self.env.company.id,
                    "country_id": self.env.ref("base.ve").id,
                }
            )
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "invoice_date": self.test_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Gravada",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [self.company_data["default_tax_purchase"].id]
                                )
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "name": "Exenta",
                            "quantity": 1.0,
                            "price_unit": 500.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [Command.set(tax_exempt.ids)],
                        }
                    ),
                ],
            }
        )
        line = self.env["account.retention.line"].new(
            {
                "move_id": bill.id,
                "economic_activity_id": self.economic_activity.id,
            }
        )
        line.onchange_economic_activity_id()
        self.assertAlmostEqual(line.invoice_amount, 1500.0, places=2)
        self.assertAlmostEqual(line.retention_amount, 75.0, places=2)

    def test_municipal_auto_create_on_post(self):
        bill = self._create_vendor_bill()
        self._add_municipal_line(bill)
        bill.action_post()
        self.assertTrue(bill.municipal_voucher_number)
        self.assertTrue(bill.municipal_retention_id)
        self.assertEqual(bill.municipal_retention_id.type_retention, "municipal")
        self.assertEqual(bill.municipal_retention_id.state, "emitted")
        self.assertAlmostEqual(
            bill.retention_municipal_line_ids.retention_amount,
            50.0,
            places=2,
        )

    def test_municipal_does_not_recreate_when_voucher_exists(self):
        bill = self._create_vendor_bill()
        self._add_municipal_line(bill)
        bill.action_post()
        first_retention = bill.municipal_retention_id
        first_number = bill.municipal_voucher_number
        bill._l10n_ve_create_post_retentions()
        self.assertEqual(bill.municipal_retention_id, first_retention)
        self.assertEqual(bill.municipal_voucher_number, first_number)
        self.assertEqual(
            self.env["account.retention"].search_count(
                [
                    ("type_retention", "=", "municipal"),
                    ("retention_line_ids.move_id", "=", bill.id),
                    ("state", "!=", "cancel"),
                ]
            ),
            1,
        )

    def test_municipal_sequence_code(self):
        sequence = self.env["account.retention"].get_sequence_municipal_retention()
        self.assertTrue(sequence)
        self.assertEqual(sequence.code, "retention.municipal.control.number")

    def test_municipal_cancel_clears_voucher_number(self):
        bill = self._create_vendor_bill()
        self._add_municipal_line(bill)
        bill.action_post()
        retention = bill.municipal_retention_id
        self.assertTrue(bill.municipal_voucher_number)
        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")
        self.assertFalse(bill.municipal_voucher_number)

    def test_validate_municipal_requires_journal(self):
        bill = self._create_vendor_bill()
        self.env.company.municipal_supplier_retention_journal_id = False
        with self.assertRaises(UserError):
            bill._validate_municipal_retention()
        self.env.company.municipal_supplier_retention_journal_id = (
            self.municipal_journal
        )

    def test_invoice_write_recalculates_municipal_line(self):
        bill = self._create_vendor_bill(price_unit=100.0)
        line = self._add_municipal_line(bill, invoice_amount=100.0)
        self.assertAlmostEqual(line.invoice_amount, 100.0, places=2)
        bill.write(
            {
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Linea extra",
                            "quantity": 1.0,
                            "price_unit": 50.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [
                                Command.set(
                                    [self.company_data["default_tax_purchase"].id]
                                )
                            ],
                        }
                    )
                ]
            }
        )
        self.assertAlmostEqual(line.invoice_amount, 150.0, places=2)
        self.assertAlmostEqual(line.retention_amount, 7.5, places=2)
        self.assertEqual(line.aliquot, 5.0)

    def test_municipal_xlsx_uses_company_amounts(self):
        bill = self._create_vendor_bill()
        self._add_municipal_line(bill)
        bill.action_post()
        table = self.env["municipal.retention.xlsx"].get_xlsx_municipal_retention(
            bill.municipal_retention_id.id
        )
        self.assertFalse(table.empty)
        self.assertAlmostEqual(table.iloc[0]["Base Imponible"], 1000.0, places=2)
        self.assertAlmostEqual(table.iloc[0]["IMPUESTO RETENIDO"], 50.0, places=2)
        self.assertNotIn("foreign_invoice_amount", table.columns)

    def test_municipal_xlsx_wizard_creation(self):
        wizard = self.env["municipal.retention.xlsx.report"].create(
            {
                "date_start": self.test_date,
                "date_end": self.test_date,
            }
        )
        self.assertTrue(wizard)
        with self.assertRaises(MissingError):
            wizard.print_xlsx()

    def test_municipal_patent_wizard_creation(self):
        wizard = self.env["municipal.retention.patent.report"].create(
            {
                "date_start": self.test_date,
                "date_end": self.test_date,
            }
        )
        self.assertTrue(wizard)
        table = wizard._get_xlsx_municipality_retention_report()
        self.assertTrue(table is not None)

    def test_open_municipal_retention_from_invoice(self):
        bill = self._create_vendor_bill()
        self._add_municipal_line(bill)
        bill.action_post()
        action = bill.action_open_municipal_retention()
        self.assertEqual(action["res_id"], bill.municipal_retention_id.id)
        self.assertEqual(action["res_model"], "account.retention")

    def test_set_voucher_number_in_invoice_municipal(self):
        bill = self._create_vendor_bill(post=True)
        retention = self.env["account.retention"].new(
            {
                "type_retention": "municipal",
                "number": "MUN-TEST-001",
            }
        )
        self.env["account.retention"].set_voucher_number_in_invoice(bill, retention)
        self.assertEqual(bill.municipal_voucher_number, "MUN-TEST-001")
