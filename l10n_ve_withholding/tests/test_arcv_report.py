from odoo import fields
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestArcvReport(L10nVeSeniatCommon):
    def test_print_arcv_uses_loaded_report_action(self):
        report = self.env.ref("l10n_ve_withholding.action_report_arcv")
        self.assertEqual(report.model, "arcv.report")
        self.assertEqual(report.report_name, "l10n_ve_withholding.report_template_arcv")
        wizard = (
            self.env["arcv.report"]
            .with_context(discard_logo_check=True)
            .create(
                {
                    "partner_id": self.partner_a.id,
                    "date_start": fields.Date.today(),
                    "date_end": fields.Date.today(),
                }
            )
        )
        action = wizard.print_arcv()
        self.assertEqual(action["type"], "ir.actions.report")
        self.assertEqual(action["report_name"], report.report_name)
        self.assertIn("retentions", action["data"])
        self.assertEqual(action["data"]["partner"]["name"], self.partner_a.name)
