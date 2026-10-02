# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.release import version


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def _get_l10n_ve_version(self):
        enterprise = (
            self.env["ir.module.module"]
            .sudo()
            .search_count(
                [("name", "=", "web_enterprise"), ("state", "=", "installed")],
                limit=1,
            )
        )
        edition = "Enterprise" if enterprise else "Community"
        return f"Odoo {edition} v{version}"

    def session_info(self):
        session = super().session_info()
        session["l10n_ve_version"] = self._get_l10n_ve_version()
        return session
