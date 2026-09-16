from odoo import Command, fields
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestRetentionPaymentOutstanding(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Proveedor outstanding retención",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J998877665",
                "supplier_rank": 1,
            }
        )
        cls.test_date = fields.Date.today()
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

    def _create_vendor_bill(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "invoice_date": self.test_date,
                "ref": "FAC-OUT-001",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Compra",
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
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def _create_draft_iva_retention(self, bill):
        return self.env["account.retention"].create(
            {
                "name": "Retención IVA outstanding",
                "type_retention": "iva",
                "type": "in_invoice",
                "partner_id": bill.partner_id.id,
                "date": self.test_date,
                "date_accounting": self.test_date,
                "retention_line_ids": [
                    Command.create(
                        {
                            "name": "Línea IVA",
                            "move_id": bill.id,
                            "invoice_amount": bill.amount_untaxed,
                            "iva_amount": bill.amount_tax,
                            "invoice_total": bill.amount_total,
                            "aliquot": 16.0,
                            "retention_amount": bill.amount_tax * 0.75,
                        }
                    )
                ],
            }
        )

    def test_ensure_outstanding_account_from_journal(self):
        self.assertTrue(self.iva_journal)
        bill = self._create_vendor_bill()
        retention = self._create_draft_iva_retention(bill)
        payment = retention.payment_ids
        self.assertTrue(payment)
        payment.outstanding_account_id = False
        self.assertFalse(payment.outstanding_account_id)

        payment._l10n_ve_ensure_retention_outstanding_account()

        expected = (
            payment.payment_method_line_id.payment_account_id
            or payment.journal_id.default_account_id
            or payment.journal_id.suspense_account_id
        )
        self.assertTrue(expected)
        self.assertEqual(payment.outstanding_account_id, expected)
