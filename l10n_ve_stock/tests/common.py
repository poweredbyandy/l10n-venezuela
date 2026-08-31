# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.addons.l10n_ve_seniat.tests import common as seniat_common
from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


class L10nVeStockCommon(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_l10n_ve_dispatch_guide_section()

    @classmethod
    def _setup_l10n_ve_dispatch_guide_section(cls):
        company = cls.env.company
        warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        if not warehouse or warehouse.l10n_ve_dispatch_guide_section_id:
            return
        book = cls.env["account.book"].create(
            {
                "name": "Talonario guias tests",
                "company_id": company.id,
                "number_from": 1,
                "number_to": 99_999_999,
                "l10n_ve_series_prefix": "01",
            }
        )
        section = cls.env["account.book.section"].create(
            {
                "book_id": book.id,
                "name": "Guias despacho",
                "number_from": 40_000_000,
                "number_to": 49_999_999,
            }
        )
        warehouse.l10n_ve_dispatch_guide_section_id = section


_l10n_ve_seniat_common_setup_class = L10nVeSeniatCommon.setUpClass.__func__


@classmethod
def _l10n_ve_seniat_common_setup_class_with_stock(cls):
    _l10n_ve_seniat_common_setup_class(cls)
    L10nVeStockCommon._setup_l10n_ve_dispatch_guide_section.__func__(cls)


seniat_common.L10nVeSeniatCommon.setUpClass = (
    _l10n_ve_seniat_common_setup_class_with_stock
)
L10nVeSeniatCommon.setUpClass = _l10n_ve_seniat_common_setup_class_with_stock
