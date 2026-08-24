# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from uuid import uuid4

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestL10nVeSeniatHttp(HttpCase):
    def test_web_login_page_contains_module_version(self):
        res = self.url_open("/web/login")
        self.assertEqual(res.status_code, 200)
        mod = (
            self.env["ir.module.module"]
            .sudo()
            .search([("name", "=", "l10n_ve_seniat")], limit=1)
        )
        self.assertTrue(mod)
        self.assertIn(mod.installed_version, res.text)

    def test_session_info_contains_l10n_ve_version(self):
        self.authenticate("admin", "admin")
        payload = json.dumps({"jsonrpc": "2.0", "method": "call", "id": str(uuid4())})
        res = self.url_open(
            "/web/session/get_session_info",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        ver = data["result"].get("l10n_ve_version", "")
        self.assertIn("Odoo", ver)
        self.assertIn("v", ver)
