from datetime import date

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestRetentionResetDraft(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_date = date(2026, 3, 15)
        cls.supplier = cls.env["res.partner"].create(
            {
                "name": "Proveedor restablecer retencion",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J998877661",
                "supplier_rank": 1,
            }
        )
        cls.customer = cls.env["res.partner"].create(
            {
                "name": "Cliente restablecer retencion",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J998877662",
                "customer_rank": 1,
            }
        )
        cls.iva_journal = cls._retention_journal(
            "iva_supplier_retention_journal_id", "RIP"
        )
        cls.municipal_journal = cls._retention_journal(
            "municipal_supplier_retention_journal_id", "RMP"
        )
        cls.env.company.municipal_customer_retention_journal_id = cls.municipal_journal

    @classmethod
    def _retention_journal(cls, company_field, code):
        journal = cls.env.company[company_field]
        if not journal:
            journal = cls.env["account.journal"].search(
                [
                    ("company_id", "=", cls.env.company.id),
                    ("code", "=", code),
                ],
                limit=1,
            )
            cls.env.company[company_field] = journal
        if (
            journal
            and not journal.default_account_id
            and not journal.outbound_payment_method_line_ids.payment_account_id
        ):
            journal.default_account_id = cls.company_data["default_account_payable"]
        return journal

    def _create_vendor_bill(self):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": self.supplier.id,
                "invoice_date": self.test_date,
                "ref": "FAC-DRAFT-001",
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

    def _create_supplier_iva_retention(self, bill):
        return self.env["account.retention"].create(
            {
                "name": "Retencion IVA proveedor",
                "type_retention": "iva",
                "type": "in_invoice",
                "partner_id": bill.partner_id.id,
                "date": self.test_date,
                "date_accounting": self.test_date,
                "retention_line_ids": [
                    Command.create(
                        {
                            "name": "Linea IVA",
                            "move_id": bill.id,
                            "invoice_amount": bill.amount_untaxed,
                            "iva_amount": bill.amount_tax,
                            "invoice_total": bill.amount_total,
                            "aliquot": 16.0,
                            "related_percentage_tax_base": 75.0,
                            "retention_amount": bill.amount_tax * 0.75,
                        }
                    )
                ],
            }
        )

    def _create_customer_invoice(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer.id,
                "invoice_date": self.test_date,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Venta",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                Command.set([self.company_data["default_tax_sale"].id])
                            ],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def test_supplier_iva_reset_keeps_number_and_can_be_emitted_again(self):
        self.assertTrue(self.iva_journal)
        bill = self._create_vendor_bill()
        retention = self._create_supplier_iva_retention(bill)
        retention.action_post()
        number = retention.number
        sequence = retention.get_sequence_iva_retention()
        sequence.invalidate_recordset(["number_next", "number_next_actual"])
        next_number = sequence.number_next_actual
        self.assertEqual(retention.state, "emitted")
        self.assertTrue(number)

        retention.action_draft()

        self.assertEqual(retention.state, "draft")
        self.assertEqual(retention.number, number)
        self.assertEqual(retention.payment_ids.state, "draft")
        sequence.invalidate_recordset(["number_next", "number_next_actual"])
        self.assertEqual(sequence.number_next_actual, next_number)

        retention.action_post()

        self.assertEqual(retention.state, "emitted")
        self.assertEqual(retention.number, number)
        self.assertEqual(bill.iva_voucher_number, number)
        sequence.invalidate_recordset(["number_next", "number_next_actual"])
        self.assertEqual(sequence.number_next_actual, next_number)
        self.assertTrue(retention.payment_ids.move_id.line_ids.filtered("reconciled"))

    def test_cleared_supplier_number_uses_last_voucher(self):
        self.assertTrue(self.iva_journal)
        first = self._create_supplier_iva_retention(self._create_vendor_bill())
        first.action_post()
        second = self._create_supplier_iva_retention(self._create_vendor_bill())
        second.action_post()
        first_index = second._retention_control_index(first.number)
        sequence = second.get_sequence_iva_retention()

        second.action_draft()
        sequence.sudo().unlink()
        second.write({"number": False, "name": False})
        second.action_post()

        self.assertEqual(second.state, "emitted")
        self.assertEqual(
            second._retention_control_index(second.number),
            first_index + 1,
        )
        synced = second.get_sequence_iva_retention()
        synced.invalidate_recordset(["number_next", "number_next_actual"])
        self.assertEqual(
            synced.number_next_actual,
            second._retention_control_index(second.number) + 1,
        )

    def test_cancelled_supplier_retention_can_be_emitted_again(self):
        bill = self._create_vendor_bill()
        retention = self._create_supplier_iva_retention(bill)
        retention.action_post()
        number = retention.number
        retention.action_cancel()
        self.assertEqual(retention.state, "cancel")

        retention.action_draft()
        self.assertEqual(retention.state, "draft")
        self.assertEqual(retention.number, number)

        retention.action_post()
        self.assertEqual(retention.state, "emitted")
        self.assertEqual(retention.number, number)
        self.assertEqual(bill.iva_voucher_number, number)

    def test_customer_retention_can_return_to_draft_and_be_emitted(self):
        invoice = self._create_customer_invoice()
        number = "20260315000099"
        retention = self.env["account.retention"].create(
            {
                "name": "Retencion municipal cliente",
                "type_retention": "municipal",
                "type": "out_invoice",
                "partner_id": self.customer.id,
                "date": self.test_date,
                "date_accounting": self.test_date,
                "number": number,
                "retention_line_ids": [
                    Command.create(
                        {
                            "name": "Linea municipal cliente",
                            "move_id": invoice.id,
                            "invoice_amount": invoice.amount_untaxed,
                            "invoice_total": invoice.amount_total,
                            "aliquot": 5.0,
                            "retention_amount": 50.0,
                        }
                    )
                ],
            }
        )
        retention.action_post()
        self.assertEqual(retention.state, "emitted")

        retention.action_draft()
        self.assertEqual(retention.state, "draft")
        self.assertEqual(retention.number, number)
        self.assertEqual(retention.payment_ids.state, "draft")

        retention.action_post()
        self.assertEqual(retention.state, "emitted")
        self.assertEqual(retention.number, number)
        self.assertEqual(invoice.municipal_voucher_number, number)
