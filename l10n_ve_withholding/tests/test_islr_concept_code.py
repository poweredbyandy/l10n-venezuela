from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestIslrConceptCode(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.concept = cls.env.ref(
            "l10n_ve_withholding.payment_concept_three_l10n_ve_withholding"
        )
        cls.type_pn = cls.env.ref(
            "l10n_ve_withholding.type_person_l10n_ve_withholding"
        )
        cls.type_pj = cls.env.ref(
            "l10n_ve_withholding.type_person_three_l10n_ve_withholding"
        )
        cls.tax_16 = cls.company_data["default_tax_purchase"]

    def _create_bill(self, partner):
        bill = self.env["account.move"].create(
            {
                "move_type": "in_invoice",
                "partner_id": partner.id,
                "invoice_date": "2026-09-16",
                "invoice_line_ids": [
                    Command.create(
                        {
                            "name": "Servicio",
                            "quantity": 1.0,
                            "price_unit": 1000.0,
                            "account_id": self.company_data[
                                "default_account_expense"
                            ].id,
                            "tax_ids": [Command.set(self.tax_16.ids)],
                        }
                    )
                ],
            }
        )
        bill.action_post()
        return bill

    def _create_line(self, partner):
        bill = self._create_bill(partner)
        return self.env["account.retention.line"].create(
            {
                "name": "ISLR",
                "move_id": bill.id,
                "payment_concept_id": self.concept.id,
                "invoice_amount": 1000.0,
                "invoice_total": 1160.0,
                "retention_amount": 20.0,
            }
        )

    def test_pj_domiciliada_uses_code_55(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Contratista PJ",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J123456789",
                "is_company": True,
                "supplier_rank": 1,
                "type_person_id": self.type_pj.id,
            }
        )
        line = self._create_line(partner)
        self.assertEqual(line.code, "55")

    def test_pn_residente_uses_code_53(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Contratista PN",
                "country_id": self.env.ref("base.ve").id,
                "vat": "V181357351",
                "supplier_rank": 1,
                "type_person_id": self.type_pn.id,
            }
        )
        line = self._create_line(partner)
        self.assertEqual(line.code, "53")
