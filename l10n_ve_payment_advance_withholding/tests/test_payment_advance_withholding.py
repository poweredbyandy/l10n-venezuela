from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestPaymentAdvanceWithholding(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_date = fields.Date.from_string("2026-07-30")
        cls.customer_advance_account = cls.env["account.account"].create(
            {
                "name": "Customer Advances WH",
                "code": "2180101",
                "account_type": "liability_current",
                "reconcile": True,
                "company_ids": [Command.set(cls.env.company.ids)],
            }
        )
        cls.supplier_advance_account = cls.env["account.account"].create(
            {
                "name": "Supplier Advances WH",
                "code": "1180101",
                "account_type": "asset_prepayments",
                "reconcile": True,
                "company_ids": [Command.set(cls.env.company.ids)],
            }
        )
        cls.retention_account = cls.env["account.account"].create(
            {
                "name": "Municipal Retention",
                "code": "2180102",
                "account_type": "liability_payable",
                "reconcile": True,
                "company_ids": [Command.set(cls.env.company.ids)],
            }
        )
        cls.env.company.write(
            {
                "account_customer_advance_id": cls.customer_advance_account.id,
                "account_supplier_advance_id": cls.supplier_advance_account.id,
            }
        )
        cls.partner = cls.partner_a
        cls.partner.with_company(cls.env.company).write(
            {
                "property_account_customer_advance_id": cls.customer_advance_account.id,
                "property_account_supplier_advance_id": cls.supplier_advance_account.id,
            }
        )
        cls.municipal_journal = cls.env["account.journal"].create(
            {
                "name": "Retencion Municipal Clientes",
                "code": "IMC",
                "type": "bank",
                "company_id": cls.env.company.id,
                "default_account_id": cls.retention_account.id,
            }
        )
        (
            cls.municipal_journal.inbound_payment_method_line_ids
            | cls.municipal_journal.outbound_payment_method_line_ids
        ).write({"payment_account_id": cls.retention_account.id})
        cls.env.company.municipal_customer_retention_journal_id = cls.municipal_journal

    def _create_customer_invoice(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "company_id": self.env.company.id,
                "journal_id": self.company_data["default_journal_sale"].id,
                "partner_id": self.partner.id,
                "invoice_date": self.test_date,
                "date": self.test_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Snack line",
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set(self.company_data["default_tax_sale"].ids)
                            ],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _create_municipal_retention(self, invoice):
        municipality = self.env["res.country.municipality"].search(
            [("country_id", "=", self.env.ref("base.ve").id)],
            limit=1,
        )
        if not municipality:
            state = self.env["res.country.state"].search(
                [("country_id", "=", self.env.ref("base.ve").id)],
                limit=1,
            )
            municipality = (
                self.env["res.country.municipality"]
                .sudo()
                .create(
                    {
                        "name": "Municipio Test WH",
                        "code": "MUN-WH-ADV",
                        "country_id": self.env.ref("base.ve").id,
                        "state_id": [Command.set(state.ids)],
                    }
                )
            )
        branch = (
            self.env["economic.branch"]
            .sudo()
            .create(
                {
                    "name": "Rama municipal advance",
                    "status": "active",
                }
            )
        )
        activity = self.env["economic.activity"].sudo().create(
            {
                "name": "Actividad municipal advance",
                "municipality_id": municipality.id,
                "branch_id": branch.id,
                "aliquot": 1.5,
                "description": "Actividad de prueba",
                "minimum_monthly": 0.0,
                "minimum_annual": 0.0,
            }
        )
        invoice_amount = invoice.amount_untaxed
        return self.env["account.retention"].create(
            {
                "type_retention": "municipal",
                "type": "out_invoice",
                "partner_id": invoice.partner_id.id,
                "date": self.test_date,
                "date_accounting": self.test_date,
                "number": "zdgrsertserg",
                "retention_line_ids": [
                    Command.create(
                        {
                            "name": "Retencion Municipal",
                            "move_id": invoice.id,
                            "economic_activity_id": activity.id,
                            "aliquot": 1.5,
                            "invoice_amount": invoice_amount,
                            "invoice_total": invoice.amount_total,
                            "retention_amount": invoice_amount * 1.5 / 100,
                        }
                    )
                ],
            }
        )

    def test_standalone_retention_payment_uses_receivable(self):
        payment = self.env["account.payment"].create(
            {
                "date": self.test_date,
                "amount": 20.72,
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.partner.id,
                "journal_id": self.municipal_journal.id,
                "payment_method_id": self.env.ref(
                    "account.account_payment_method_manual_in"
                ).id,
                "is_retention": True,
                "payment_type_retention": "municipal",
            }
        )
        self.assertEqual(
            payment.destination_account_id,
            self.partner.property_account_receivable_id,
        )
        payment.action_post()
        receivable_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        advance_lines = payment.move_id.line_ids.filtered(
            lambda line: line.account_id == self.customer_advance_account
        )
        self.assertTrue(receivable_lines)
        self.assertFalse(advance_lines)

    def test_municipal_customer_retention_posts_against_receivable(self):
        invoice = self._create_customer_invoice()
        retention = self._create_municipal_retention(invoice)
        retention.action_post()
        payment = retention.payment_ids
        self.assertEqual(retention.state, "emitted")
        self.assertTrue(payment.is_retention)
        self.assertEqual(
            payment.destination_account_id,
            self.partner.property_account_receivable_id,
        )
        self.assertTrue(
            payment.move_id.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
            )
        )
        self.assertFalse(
            payment.move_id.line_ids.filtered(
                lambda line: line.account_id == self.customer_advance_account
            )
        )
