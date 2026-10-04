# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged
from odoo.tools import convert_file

from ..hooks import post_init_hook, pre_init_hook


@tagged("post_install", "-at_install")
class TestHooks(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env.ref("l10n_ve_seniat_user.user_seniat")
        cls.partner = cls.env.ref("l10n_ve_seniat_user.partner_seniat")

    def _xmlid_modules(self):
        self.env.cr.execute(
            """
            SELECT name, module
              FROM ir_model_data
             WHERE name IN ('partner_seniat', 'user_seniat')
             ORDER BY name
            """
        )
        return self.env.cr.fetchall()

    def _set_xmlid_module(self, module):
        self.env.cr.execute(
            """
            UPDATE ir_model_data
               SET module = %s
             WHERE name IN ('partner_seniat', 'user_seniat')
               AND module IN ('l10n_ve_seniat', 'l10n_ve_seniat_user')
            """,
            (module,),
        )
        self.env.registry.clear_cache()

    def _delete_xmlids(self):
        self.env.cr.execute(
            """
            DELETE FROM ir_model_data
             WHERE name IN ('partner_seniat', 'user_seniat')
               AND module IN ('l10n_ve_seniat', 'l10n_ve_seniat_user')
            """
        )
        self.env.registry.clear_cache()

    def _install(self):
        pre_init_hook(self.env)
        convert_file(
            self.env,
            "l10n_ve_seniat_user",
            "data/res_users_seniat.xml",
            {},
            mode="init",
            kind="data",
        )
        post_init_hook(self.env)
        self.env.registry.clear_cache()
        self.env.invalidate_all()

    def test_user_data(self):
        self.assertEqual(self.user.login, "seniat")
        self.assertEqual(self.user.partner_id, self.partner)
        self.assertEqual(self.partner.vat, "G200003030")
        self.assertTrue(self.user.has_group("l10n_ve_seniat.group_seniat"))
        self.assertTrue(self.user.has_group("l10n_ve_seniat.group_seniat_readonly"))

    def test_existing_user_keeps_its_configuration(self):
        extra_group = self.env.ref("base.group_no_one")
        self.user.write({"groups_id": [(4, extra_group.id)], "active": True})
        self.partner.email = "auditor@example.com"
        groups = self.user.groups_id
        self._set_xmlid_module("l10n_ve_seniat")
        self._install()
        self.assertEqual(
            self._xmlid_modules(),
            [
                ("partner_seniat", "l10n_ve_seniat_user"),
                ("user_seniat", "l10n_ve_seniat_user"),
            ],
        )
        self.assertEqual(self.env.ref("l10n_ve_seniat_user.user_seniat"), self.user)
        self.assertTrue(self.user.active)
        self.assertEqual(self.user.groups_id, groups)
        self.assertEqual(self.partner.email, "auditor@example.com")

    def test_archived_user_stays_archived(self):
        self.user.active = False
        self._set_xmlid_module("l10n_ve_seniat")
        self._install()
        self.assertFalse(self.user.active)

    def test_user_without_xmlid_is_adopted(self):
        self._delete_xmlids()
        self._install()
        self.assertEqual(self.env.ref("l10n_ve_seniat_user.user_seniat"), self.user)
        self.assertEqual(
            self.env.ref("l10n_ve_seniat_user.partner_seniat"), self.partner
        )
        self.assertEqual(
            self.env["res.users"]
            .with_context(active_test=False)
            .search([("login", "=", "seniat")]),
            self.user,
        )

    def test_missing_user_is_created(self):
        self._delete_xmlids()
        self.user.login = "seniat_old"
        self._install()
        user = self.env.ref("l10n_ve_seniat_user.user_seniat").with_context(
            active_test=False
        )
        self.assertNotEqual(user, self.user)
        self.assertEqual(user.login, "seniat")
        self.assertFalse(user.active)
        self.assertEqual(user.partner_id.vat, "G200003030")
        self.assertTrue(user.has_group("l10n_ve_seniat.group_seniat"))
