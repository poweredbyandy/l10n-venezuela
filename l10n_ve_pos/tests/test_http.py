import json
from uuid import uuid4

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestL10nVePosHttp(HttpCase):
    def test_session_info_contains_l10n_ve_version_for_pos_stack(self):
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
