# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""ISLR matching by (person type, ISLR category) and history freeze."""

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestIslrPersonTypeMatching(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ve = cls.env.ref("base.ve")
        cls.concept_three = cls.env.ref(
            "l10n_ve_withholding.payment_concept_three_l10n_ve_withholding"
        )
        cls.concept_six = cls.env.ref(
            "l10n_ve_withholding.payment_concept_six_l10n_ve_withholding"
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

    def _create_line(self, partner, concept):
        bill = self._create_bill(partner)
        return self.env["account.retention.line"].create(
            {
                "name": "ISLR",
                "move_id": bill.id,
                "payment_concept_id": concept.id,
                "invoice_amount": 1000.0,
                "invoice_total": 1160.0,
                "retention_amount": 20.0,
            }
        )

    def _create_partner(self, **values):
        return self.env["res.partner"].create(
            {"name": "Proveedor", "country_id": self.ve.id, **values}
        )

    def test_pnnr_uses_code_54(self):
        partner = self._create_partner(vat="P1234567", supplier_rank=1)
        self.assertEqual(partner.l10n_ve_person_type, "pn_non_resident")
        line = self._create_line(partner, self.concept_three)
        self.assertEqual(line.code, "54")

    def test_pjnd_uses_code_56(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Proveedor extranjero",
                "country_id": self.env.ref("base.us").id,
                "vat": "J123456789",
                "is_company": True,
                "supplier_rank": 1,
            }
        )
        self.assertEqual(partner.l10n_ve_person_type, "pj_non_domiciled")
        line = self._create_line(partner, self.concept_three)
        self.assertEqual(line.code, "56")

    def test_radio_broadcaster_matches_special_line(self):
        partner = self._create_partner(vat="J123456789", supplier_rank=1)
        partner.l10n_ve_islr_category = "radio_broadcaster"
        line = self._create_line(partner, self.concept_six)
        self.assertEqual(line.code, "86")

    def test_special_category_falls_back_to_standard_line(self):
        """A radio broadcaster retained under a concept without a special
        line falls back to the standard row of its person type."""
        partner = self._create_partner(vat="J123456789", supplier_rank=1)
        partner.l10n_ve_islr_category = "radio_broadcaster"
        line = self._create_line(partner, self.concept_three)
        self.assertEqual(line.code, "55")

    def test_normalize_islr_category_helper(self):
        normalize = self.env["res.partner"]._l10n_ve_normalize_islr_category
        self.assertEqual(
            normalize("pj_domiciled", "radio_broadcaster"), "radio_broadcaster"
        )
        self.assertEqual(
            normalize("pj_domiciled", "financial_institution"), "standard"
        )
        self.assertEqual(
            normalize("pj_non_domiciled", "financial_institution"),
            "financial_institution",
        )
        self.assertEqual(
            normalize("pj_non_domiciled", "radio_broadcaster"), "standard"
        )
        self.assertEqual(normalize("pn_resident", "radio_broadcaster"), "standard")
        self.assertEqual(normalize(False, False), "standard")

    def test_stale_category_is_neutralized_by_fallback(self):
        """A nonsense category stored by an import cannot misprice: the
        matcher falls back to the standard line of the person type."""
        partner = self._create_partner(vat="V181357351", supplier_rank=1)
        partner.write({"l10n_ve_islr_category": "radio_broadcaster"})
        line = self._create_line(partner, self.concept_six)
        self.assertEqual(line.code, "83")

    def test_category_reset_follows_person_type_change(self):
        partner = self._create_partner(vat="J123456789", supplier_rank=1)
        partner.write({"l10n_ve_islr_category": "radio_broadcaster"})
        self.assertEqual(partner.l10n_ve_islr_category, "radio_broadcaster")
        # The RIF now says persona natural: radio no longer applies.
        partner.write({"vat": "V181357351"})
        self.assertEqual(partner.l10n_ve_person_type, "pn_resident")
        self.assertEqual(partner.l10n_ve_islr_category, "standard")

    def test_emitted_retention_code_is_frozen(self):
        """docs/adr/0002: a reclassification must not rewrite declared
        retentions; draft lines follow the new classification."""
        partner = self._create_partner(vat="J123456789", supplier_rank=1)
        line = self._create_line(partner, self.concept_three)
        self.assertEqual(line.code, "55")
        amount = line.retention_amount

        retention = self.env["account.retention"].create(
            {
                "partner_id": partner.id,
                "type_retention": "islr",
                "type": "in_invoice",
                "retention_line_ids": [Command.link(line.id)],
            }
        )
        retention.state = "emitted"

        # Now the supplier turns out to be a natural person resident.
        partner.write({"vat": "V181357351"})
        self.assertEqual(partner.l10n_ve_person_type, "pn_resident")

        # The emitted line keeps its declared code and amount...
        self.assertEqual(line.code, "55")
        self.assertEqual(line.retention_amount, amount)

        # ...while a draft line recalculates with the new classification.
        draft_line = self._create_line(partner, self.concept_three)
        draft = self.env["account.retention"].create(
            {
                "partner_id": partner.id,
                "type_retention": "islr",
                "type": "in_invoice",
                "retention_line_ids": [Command.link(draft_line.id)],
            }
        )
        self.assertEqual(draft.state, "draft")
        self.assertEqual(draft_line.code, "53")
