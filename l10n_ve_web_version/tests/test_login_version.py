# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestOdooVersionLogin(HttpCase):
    def test_web_login_page_contains_odoo_version(self):
        expected = self.env["ir.http"]._get_l10n_ve_version()
        res = self.url_open("/web/login")
        self.assertEqual(res.status_code, 200)
        self.assertRegex(
            res.text,
            rf'<small[^>]*class="text-muted"[^>]*>{re.escape(expected)}</small>',
        )
