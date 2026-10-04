# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.state = cls.env.ref("l10n_ve_address.res_country_state_1")
        cls.municipality = cls.env.ref("l10n_ve_address.res_country_municipality_1")
        cls.parish = cls.env["res.country.parish"].search(
            [("municipality_id", "=", cls.municipality.id)], limit=1
        )

    def test_preloaded_data(self):
        self.assertEqual(self.state.country_id, self.env.ref("base.ve"))
        self.assertIn(self.state, self.municipality.state_id)
        self.assertTrue(self.parish)

    def test_onchange_municipality_clears_parish(self):
        partner = self.env["res.partner"].new(
            {
                "name": "Test",
                "municipality_id": self.municipality.id,
                "parish_id": self.parish.id,
            }
        )
        partner._onchange_municipality_id()
        self.assertFalse(partner.parish_id)

    def test_onchange_state_clears_municipality_and_parish(self):
        partner = self.env["res.partner"].new(
            {
                "name": "Test",
                "state_id": self.state.id,
                "municipality_id": self.municipality.id,
                "parish_id": self.parish.id,
            }
        )
        partner._onchange_state_id()
        self.assertFalse(partner.municipality_id)
        self.assertFalse(partner.parish_id)
