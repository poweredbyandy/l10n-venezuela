# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from uuid import uuid4

from odoo.tests import HttpCase, tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeEmissionMediumContext(L10nVeSeniatCommon):
    def test_company_emission_medium_codes_come_from_sale_journals(self):
        company = self.env.company
        journal = self.company_data["default_journal_sale"]
        self.assertEqual(company._l10n_ve_emission_medium_codes(), ("free_form",))
        self.assertTrue(company._l10n_ve_has_emission_medium("free_form"))
        self.assertFalse(company._l10n_ve_has_emission_medium("fiscal_machine"))

        self._l10n_ve_configure_journal_digital(journal)
        self.assertEqual(company._l10n_ve_emission_medium_codes(), ("digital_billing",))

        journal.l10n_ve_emission_medium = "contingency"
        self.assertEqual(company._l10n_ve_emission_medium_codes(), ("contingency",))

        self.company_data["default_journal_purchase"].l10n_ve_emission_medium = "free"
        self.assertEqual(company._l10n_ve_emission_medium_codes(), ("contingency",))

        journal.l10n_ve_emission_medium = False
        self.assertEqual(company._l10n_ve_emission_medium_codes(), ())

    def test_company_combines_journal_mediums(self):
        company = self.env.company
        digital_journal = self.company_data["default_journal_sale"].copy(
            {"name": "Ventas digital", "code": "VDIG"}
        )
        self._l10n_ve_configure_journal_digital(digital_journal)
        self.assertEqual(
            company._l10n_ve_emission_medium_codes(),
            ("digital_billing", "free_form"),
        )


@tagged("post_install", "-at_install")
class TestL10nVeEmissionMediumSession(HttpCase):
    def _set_company_sale_medium(self, company, medium):
        journals = self.env["account.journal"].search(
            [("company_id", "=", company.id), ("type", "=", "sale")]
        )
        journals.write({"l10n_ve_emission_medium": False})
        if not medium:
            return
        vals = {
            "name": f"Ventas {medium}",
            "code": "VEM%s" % company.id,
            "type": "sale",
            "company_id": company.id,
            "l10n_ve_emission_medium": medium,
        }
        if medium == "fiscal_machine":
            vals["l10n_ve_fiscal_machine_id"] = (
                self.env["l10n.ve.fiscal.machine"]
                .create(
                    {
                        "name": "HTTP Fiscal Machine",
                        "company_id": company.id,
                        "registered_serial": "HTTPMENU%s" % company.id,
                    }
                )
                .id
            )
        self.env["account.journal"].create(vals)

    def test_session_info_contains_emission_medium_codes(self):
        company = self.env.company
        self._set_company_sale_medium(company, "digital")
        self.authenticate("admin", "admin")
        payload = json.dumps({"jsonrpc": "2.0", "method": "call", "id": str(uuid4())})
        res = self.url_open(
            "/web/session/get_session_info",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()["result"]
        self.assertIn("digital_billing", data.get("l10n_ve_emission_medium_codes", []))
        self.assertIn(
            "digital_billing",
            data.get("user_context", {}).get("l10n_ve_emission_medium_codes", []),
        )
        by_company = data.get("l10n_ve_emission_medium_codes_by_company", {})
        self.assertIn(
            "digital_billing",
            by_company.get(company.id, by_company.get(str(company.id), [])),
        )

    def test_load_menus_uses_cids_cookie_company(self):
        menu = self.env.ref(
            "l10n_ve_fiscal_serial.menu_seniat_fiscal_machines",
            raise_if_not_found=False,
        )
        if not menu:
            self.skipTest("l10n_ve_fiscal_serial is not installed.")
        default_company = self.env.ref("base.main_company")
        other = self.env["res.company"].create(
            {"name": "HTTP Cids Menu Co", "country_id": self.env.ref("base.ve").id}
        )
        self._set_company_sale_medium(default_company, False)
        self._set_company_sale_medium(other, "fiscal_machine")
        admin = self.env.ref("base.user_admin")
        admin.write(
            {
                "company_id": default_company.id,
                "company_ids": [(4, other.id)],
                "groups_id": [(4, self.env.ref("l10n_ve_seniat.group_seniat").id)],
            }
        )
        self.authenticate("admin", "admin")
        self.env.registry.clear_cache()
        self.opener.cookies["cids"] = str(default_company.id)
        res_default = self.url_open("/web/webclient/load_menus/test-default")
        self.assertEqual(res_default.status_code, 200)
        menus_default = res_default.json()
        self.assertNotIn(str(menu.id), menus_default)
        self.assertNotIn(menu.id, menus_default)

        self.opener.cookies["cids"] = str(other.id)
        res_other = self.url_open("/web/webclient/load_menus/test-other")
        self.assertEqual(res_other.status_code, 200)
        menus_other = res_other.json()
        self.assertTrue(
            str(menu.id) in menus_other or menu.id in menus_other,
            "Fiscal machines menu must appear when cids points to fiscal company",
        )
