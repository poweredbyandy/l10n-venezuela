# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class L10nVeSeniatCommon(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.partner_id.write(
            {"vat": "J770023598", "country_id": cls.env.ref("base.ve").id}
        )
        cls.change_company_country(cls.env.company, cls.env.ref("base.ve"))
        cls._setup_l10n_ve_sale_journal_sections()

    @classmethod
    def _setup_l10n_ve_sale_journal_sections(cls):
        company = cls.env.company
        journal = cls.company_data["default_journal_sale"]
        book = cls.env["account.book"].create(
            {
                "name": "Talonario tests",
                "company_id": company.id,
                "number_from": 1,
                "number_to": 99_999_999,
            }
        )
        sec = cls.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "Ventas",
                "number_from": 1,
                "number_to": 99_999_999,
            }
        )
        journal.write(
            {
                "l10n_ve_invoice_section_id": sec.id,
                "l10n_ve_credit_note_section_id": sec.id,
            }
        )
