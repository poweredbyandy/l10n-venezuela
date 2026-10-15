from datetime import date

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestRetentionNoExchangeDiff(L10nVeSeniatCommon):
    """Retention reconciliation must not create FX difference moves."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ves = cls.env.ref("base.VES")
        cls.usd = cls.env.ref("base.USD")
        cls.ves.active = True
        cls.usd.active = True
        cls.env.company.currency_id = cls.ves

        cls.invoice_date = date(2026, 1, 10)
        cls.reception_date = date(2026, 2, 15)
        cls._set_usd_rate(cls.invoice_date, 40.0)
        cls._set_usd_rate(cls.reception_date, 50.0)

        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Proveedor reten FX",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J112233445",
                "supplier_rank": 1,
            }
        )
        cls.iva_journal = cls.env.company.iva_supplier_retention_journal_id
        if not cls.iva_journal:
            cls.iva_journal = cls.env["account.journal"].search(
                [
                    ("company_id", "=", cls.env.company.id),
                    ("code", "=", "RIP"),
                ],
                limit=1,
            )
            cls.env.company.iva_supplier_retention_journal_id = cls.iva_journal
        if (
            cls.iva_journal
            and not cls.iva_journal.default_account_id
            and not cls.iva_journal.outbound_payment_method_line_ids.payment_account_id
        ):
            cls.iva_journal.default_account_id = cls.company_data[
                "default_account_payable"
            ]

    @classmethod
    def _set_usd_rate(cls, rate_date, inverse_rate):
        rate = cls.env["res.currency.rate"].search(
            [
                ("name", "=", rate_date),
                ("currency_id", "=", cls.usd.id),
                ("company_id", "=", cls.env.company.id),
            ],
            limit=1,
        )
        if rate:
            rate.inverse_company_rate = inverse_rate
        else:
            cls.env["res.currency.rate"].create(
                {
                    "name": rate_date,
                    "currency_id": cls.usd.id,
                    "company_id": cls.env.company.id,
                    "inverse_company_rate": inverse_rate,
                }
            )

    def _create_usd_vendor_bill(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "invoice_date": self.invoice_date,
                "date": self.invoice_date,
                "currency_id": self.usd.id,
                "ref": "FAC-FX-001",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Compra USD",
                            "quantity": 1.0,
                            "price_unit": 100.0,
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
        bill.action_post()
        return bill

    def _create_and_post_iva_retention(self, bill):
        # Retention amounts are stored/paid in company currency.
        iva_company = abs(bill.amount_tax_signed)
        untaxed_company = abs(bill.amount_untaxed_signed)
        total_company = abs(bill.amount_total_signed)
        retention = self.env["account.retention"].create(
            {
                "name": "Retención IVA sin FX",
                "type_retention": "iva",
                "type": "in_invoice",
                "partner_id": bill.partner_id.id,
                "date": self.reception_date,
                "date_accounting": self.reception_date,
                "number": "20260215000001",
                "retention_line_ids": [
                    Command.create(
                        {
                            "name": "Línea IVA",
                            "move_id": bill.id,
                            "invoice_amount": untaxed_company,
                            "iva_amount": iva_company,
                            "invoice_total": total_company,
                            "aliquot": 16.0,
                            "related_percentage_tax_base": 75.0,
                            "retention_amount": iva_company * 0.75,
                        }
                    )
                ],
            }
        )
        retention.with_context(skip_is_manually_modified=True).action_post()
        return retention

    def test_retention_reconcile_does_not_create_exchange_diff(self):
        self.assertTrue(self.iva_journal)
        bill = self._create_usd_vendor_bill()
        retention = self._create_and_post_iva_retention(bill)
        payment = retention.payment_ids
        self.assertTrue(payment)
        self.assertEqual(payment.date, self.reception_date)

        payable_lines = bill.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        partials = payable_lines.matched_debit_ids | payable_lines.matched_credit_ids
        self.assertTrue(partials)
        self.assertFalse(partials.filtered("exchange_move_id"))
