# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged

from ..hooks import pre_init_hook


@tagged("post_install", "-at_install")
class TestHooks(TransactionCase):
    _models = {
        "model_res_country_parish": "ir.model",
        "field_res_partner__municipality_id": "ir.model.fields",
        "res_country_state_1": "res.country.state",
        "res_country_municipality_1": "res.country.municipality",
        "res_country_parish_1": "res.country.parish",
    }

    def _xmlid_module(self, name):
        self.env.cr.execute(
            "SELECT module FROM ir_model_data WHERE name = %s AND model = %s",
            (name, self._models[name]),
        )
        return {row[0] for row in self.env.cr.fetchall()}

    def test_pre_init_hook_takes_over_seniat_records(self):
        if not self.env["ir.module.module"].search(
            [("name", "=", "l10n_ve_seniat"), ("state", "=", "installed")]
        ):
            self.skipTest("l10n_ve_seniat is not installed")
        municipality = self.env.ref("l10n_ve_address.res_country_municipality_1")
        self.env.cr.execute(
            """
            UPDATE ir_model_data
               SET module = 'l10n_ve_seniat'
             WHERE module = 'l10n_ve_address'
               AND name = ANY(%s)
            """,
            (list(self._models),),
        )
        self.env.cr.execute(
            """
            UPDATE ir_model_relation
               SET module = (
                    SELECT id FROM ir_module_module WHERE name = 'l10n_ve_seniat'
               )
             WHERE name = 'res_country_municipality_res_country_state_rel'
            """
        )
        self.env.invalidate_all()
        pre_init_hook(self.env)
        for name in self._models:
            self.assertEqual(self._xmlid_module(name), {"l10n_ve_address"}, name)
        self.env.cr.execute(
            """
            SELECT module.name
              FROM ir_model_relation relation
              JOIN ir_module_module module ON module.id = relation.module
             WHERE relation.name = 'res_country_municipality_res_country_state_rel'
            """
        )
        self.assertEqual(
            {row[0] for row in self.env.cr.fetchall()}, {"l10n_ve_address"}
        )
        self.env.registry.clear_cache()
        self.assertEqual(
            self.env.ref("l10n_ve_address.res_country_municipality_1"), municipality
        )
