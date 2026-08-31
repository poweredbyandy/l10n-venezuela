from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestRetentionVoucherText(L10nVeSeniatCommon):
    def test_iva_voucher_cites_snat_2025_providencia(self):
        view = self.env.ref("l10n_ve_withholding.report_iva_customer")
        self.assertIn("snat/2025/000054", view.arch_db)
        self.assertIn("43.171", view.arch_db)
        self.assertNotIn("Nro 1.436", view.arch_db)

    def test_islr_voucher_cites_decreto_1808(self):
        view = self.env.ref("l10n_ve_withholding.report_islr_customer")
        self.assertIn("36.203", view.arch_db)
        self.assertIn("12 de mayo", view.arch_db)
        self.assertIn("1997", view.arch_db)
