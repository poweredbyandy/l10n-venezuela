# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from uuid import uuid4

from odoo.release import version
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestL10nVeWebVersionHttp(HttpCase):
    def test_session_info_contains_odoo_version(self):
        self.authenticate("admin", "admin")
        payload = json.dumps({"jsonrpc": "2.0", "method": "call", "id": str(uuid4())})
        res = self.url_open(
            "/web/session/get_session_info",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(res.status_code, 200)
        ver = res.json()["result"].get("l10n_ve_version", "")
        self.assertRegex(ver, r"^Odoo (Community|Enterprise) v")
        self.assertTrue(ver.endswith(f"v{version}"))
