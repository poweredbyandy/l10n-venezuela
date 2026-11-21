# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVePersonType(L10nVeSeniatCommon):
    """Derivation matrix for nature/residence/person_type (docs/adr/0001)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ve = cls.env.ref("base.ve")
        cls.us = cls.env.ref("base.us")

    def _create_partner(self, **values):
        return self.env["res.partner"].create({"name": "Contacto", **values})

    # -- nature -------------------------------------------------------------

    def test_juridical_rif_is_legal(self):
        partner = self._create_partner(country_id=self.ve.id, vat="J123456789")
        self.assertEqual(partner.l10n_ve_person_nature, "legal")
        self.assertEqual(partner.l10n_ve_person_type, "pj_domiciled")

    def test_government_rif_is_legal(self):
        partner = self._create_partner(country_id=self.ve.id, vat="G123456789")
        self.assertEqual(partner.l10n_ve_person_nature, "legal")

    def test_consejo_comunal_rif_is_legal(self):
        partner = self._create_partner(country_id=self.ve.id, vat="C123456789")
        self.assertEqual(partner.l10n_ve_person_nature, "legal")

    def test_venezolano_rif_is_natural(self):
        partner = self._create_partner(country_id=self.ve.id, vat="V7440703")
        self.assertEqual(partner.l10n_ve_person_nature, "natural")
        self.assertEqual(partner.l10n_ve_person_type, "pn_resident")

    def test_extranjero_rif_is_natural_resident(self):
        # 'E' (cédula de extranjería) is treated as resident by default.
        partner = self._create_partner(country_id=self.ve.id, vat="E81234567")
        self.assertEqual(partner.l10n_ve_person_nature, "natural")
        self.assertEqual(partner.l10n_ve_person_type, "pn_resident")

    def test_pasaporte_rif_is_natural_non_resident(self):
        partner = self._create_partner(country_id=self.ve.id, vat="P1234567")
        self.assertEqual(partner.l10n_ve_person_nature, "natural")
        self.assertEqual(partner.l10n_ve_tax_residence, "non_resident")
        self.assertEqual(partner.l10n_ve_person_type, "pn_non_resident")

    def test_foreign_vat_falls_back_to_is_company(self):
        # "GB123456789" is not a RIF: no fake 'G' kind, is_company decides.
        company = self._create_partner(
            country_id=self.us.id, vat="GB123456789", is_company=True
        )
        person = self._create_partner(
            country_id=self.us.id, vat="GB123456789", is_company=False
        )
        self.assertEqual(company.l10n_ve_person_nature, "legal")
        self.assertEqual(person.l10n_ve_person_nature, "natural")

    def test_empty_vat_falls_back_to_is_company(self):
        partner = self._create_partner(country_id=self.ve.id, is_company=True)
        self.assertEqual(partner.l10n_ve_person_nature, "legal")
        self.assertEqual(partner.l10n_ve_person_type, "pj_domiciled")

    # -- residence ----------------------------------------------------------

    def test_ve_country_defaults_to_resident(self):
        partner = self._create_partner(country_id=self.ve.id, vat="J123456789")
        self.assertEqual(partner.l10n_ve_tax_residence, "resident")

    def test_foreign_country_defaults_to_non_resident(self):
        partner = self._create_partner(
            country_id=self.us.id, vat="J123456789", is_company=True
        )
        self.assertEqual(partner.l10n_ve_tax_residence, "non_resident")
        self.assertEqual(partner.l10n_ve_person_type, "pj_non_domiciled")

    def test_residence_name_follows_nature(self):
        legal = self._create_partner(country_id=self.ve.id, vat="J123456789")
        natural = self._create_partner(country_id=self.ve.id, vat="V7440703")
        self.assertEqual(legal.l10n_ve_tax_residence_name, "Domiciliada")
        self.assertEqual(natural.l10n_ve_tax_residence_name, "Residente")
        legal.l10n_ve_tax_residence = "non_resident"
        self.assertEqual(legal.l10n_ve_tax_residence_name, "No Domiciliada")

    # -- manual choice ------------------------------------------------------

    def test_manual_residence_is_kept_on_plain_write(self):
        partner = self._create_partner(country_id=self.ve.id, vat="V7440703")
        partner.write({"l10n_ve_tax_residence": "non_resident"})
        self.assertEqual(partner.l10n_ve_person_type, "pn_non_resident")
        # An unrelated write must not touch the manual choice.
        partner.write({"name": "Otro nombre"})
        self.assertEqual(partner.l10n_ve_tax_residence, "non_resident")

    def test_residence_follows_vat_change_unless_sent_explicitly(self):
        partner = self._create_partner(country_id=self.ve.id, vat="V7440703")
        partner.write({"l10n_ve_tax_residence": "non_resident"})
        self.assertEqual(partner.l10n_ve_person_type, "pn_non_resident")
        # The RIF now says jurídica and the write does not carry the
        # residence: it is recalculated (the form sends it when the user
        # chose it on screen).
        partner.write({"vat": "J123456789"})
        self.assertEqual(partner.l10n_ve_person_type, "pj_domiciled")
        # ...but when the client sends the residence together, it wins.
        partner.write({"vat": "V7440703", "l10n_ve_tax_residence": "non_resident"})
        self.assertEqual(partner.l10n_ve_person_type, "pn_non_resident")

    def test_country_change_recalculates_residence(self):
        partner = self._create_partner(
            country_id=self.us.id, vat="J123456789", is_company=True
        )
        self.assertEqual(partner.l10n_ve_person_type, "pj_non_domiciled")
        partner.write({"country_id": self.ve.id})
        self.assertEqual(partner.l10n_ve_tax_residence, "resident")
        self.assertEqual(partner.l10n_ve_person_type, "pj_domiciled")

    def test_create_with_explicit_residence_wins(self):
        partner = self._create_partner(
            country_id=self.us.id,
            vat="J123456789",
            is_company=True,
            l10n_ve_tax_residence="resident",
        )
        self.assertEqual(partner.l10n_ve_person_type, "pj_domiciled")

    def test_recompute_action_resets_residence_default(self):
        partner = self._create_partner(country_id=self.ve.id, vat="P1234567")
        self.assertEqual(partner.l10n_ve_tax_residence, "non_resident")
        partner.write({"l10n_ve_tax_residence": "resident"})
        self.assertEqual(partner.l10n_ve_tax_residence, "resident")
        partner.action_l10n_ve_recompute_tax_residence()
        self.assertEqual(partner.l10n_ve_tax_residence, "non_resident")

    def test_child_contact_gets_own_residence(self):
        parent = self._create_partner(country_id=self.ve.id, vat="J123456789")
        child = self.env["res.partner"].create(
            {
                "name": "Hija",
                "parent_id": parent.id,
                "country_id": self.us.id,
            }
        )
        self.assertEqual(parent.l10n_ve_tax_residence, "resident")
        self.assertEqual(child.l10n_ve_tax_residence, "non_resident")
