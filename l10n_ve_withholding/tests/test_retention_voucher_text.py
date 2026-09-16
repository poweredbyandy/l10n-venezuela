from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestRetentionVoucherText(L10nVeSeniatCommon):
    def test_iva_voucher_cites_snat_2025_providencia(self):
        view = self.env.ref("l10n_ve_withholding.report_iva_customer")
        self.assertIn("snat/2025/000054", view.arch_db.lower())
        self.assertIn("43.171", view.arch_db)
        self.assertNotIn("Nro 1.436", view.arch_db)

    def test_islr_voucher_cites_decreto_1808(self):
        view = self.env.ref("l10n_ve_withholding.report_islr_customer")
        self.assertIn("36.203", view.arch_db)
        self.assertIn("12 de mayo", view.arch_db)
        self.assertIn("1997", view.arch_db)

    def test_iva_voucher_company_address_wraps(self):
        view = self.env.ref("l10n_ve_withholding.report_iva_customer")
        self.assertIn("_l10n_ve_fiscal_address", view.arch_db)
        self.assertIn("overflow-wrap:break-word", view.arch_db)

    def test_islr_voucher_company_address_wraps(self):
        view = self.env.ref("l10n_ve_withholding.report_islr_customer")
        self.assertIn("_l10n_ve_fiscal_address", view.arch_db)
        self.assertIn("overflow-wrap:break-word", view.arch_db)

    def test_fiscal_address_uses_state_name_not_code(self):
        state = self.env["res.country.state"].create(
            {
                "name": "Miranda",
                "code": "XYZ-M",
                "country_id": self.env.ref("base.ve").id,
            }
        )
        partner = self.env["res.partner"].create(
            {
                "name": "Direccion Fiscal",
                "street": "Av Francisco de Miranda",
                "street2": "Torre Europa",
                "city": "Caracas",
                "state_id": state.id,
                "country_id": self.env.ref("base.ve").id,
            }
        )
        address = partner._l10n_ve_fiscal_address()
        self.assertIn("Miranda", address)
        self.assertNotIn("XYZ-M", address)
