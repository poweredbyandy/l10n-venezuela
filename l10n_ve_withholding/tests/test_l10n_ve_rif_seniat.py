from odoo import fields
from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeRifSeniatFormat(L10nVeSeniatCommon):
    def test_format_rif_full_vat_without_duplicate_prefix(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Proveedor RIF completo",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J556677889",
                "supplier_rank": 1,
            }
        )
        self.assertEqual(partner.prefix_vat, "J")
        self.assertEqual(partner._l10n_ve_format_rif_seniat(), "J556677889")

    def test_format_rif_strips_separators(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Proveedor RIF con guion",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J-556677889",
                "supplier_rank": 1,
            }
        )
        self.assertEqual(partner._l10n_ve_format_rif_seniat(), "J556677889")

    def test_arcv_report_partner_rif_without_duplicate_prefix(self):
        partner = self.env["res.partner"].create(
            {
                "name": "Proveedor ARCV",
                "country_id": self.env.ref("base.ve").id,
                "vat": "J112233445",
                "supplier_rank": 1,
            }
        )
        wizard = self.env["arcv.report"].create(
            {
                "partner_id": partner.id,
                "date_start": fields.Date.today(),
                "date_end": fields.Date.today(),
            }
        )
        data = wizard._construct_report_data({})
        self.assertEqual(data["partner"]["vat"], "J112233445")
