# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeEmissionMediumContext(L10nVeSeniatCommon):
    def test_company_emission_medium_codes_from_journals(self):
        company = self.env.company
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_fiscal_machine(journal)
        self.assertEqual(company._l10n_ve_emission_medium_codes(), ("fiscal_machine",))
        self.assertTrue(company._l10n_ve_has_emission_medium("fiscal_machine"))
        self.assertFalse(company._l10n_ve_has_emission_medium("free_form"))
        self._l10n_ve_configure_journal_free(journal)
        self.assertEqual(company._l10n_ve_emission_medium_codes(), ("free_form",))
        self.assertTrue(company._l10n_ve_has_emission_medium("free_form"))
        self.assertFalse(company._l10n_ve_has_emission_medium("fiscal_machine"))
