# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.tests import tagged
from odoo.tools.misc import formatLang

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestInvoiceExchangeRateDisplay(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner VE",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J12345678",
            }
        )

    def _invoice_vals(self, currency):
        return {
            "move_type": "out_invoice",
            "partner_id": self.partner_ve.id,
            "currency_id": currency.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": "Test line",
                        "quantity": 1.0,
                        "price_unit": 100.0,
                        "account_id": self.company_data["default_account_revenue"].id,
                        "tax_ids": [
                            (6, 0, [self.company_data["default_tax_sale"].id])
                        ],
                    },
                )
            ],
        }

    def test_printed_rate_uses_four_decimals(self):
        company_currency = self.env.company.currency_id
        local = self.env["account.move"].create(self._invoice_vals(company_currency))
        self.assertFalse(local.l10n_ve_report_exchange_rate_display())

        foreign_currency = self.env.ref("base.USD")
        if foreign_currency == company_currency:
            foreign_currency = self.env.ref("base.EUR")
        foreign = self.env["account.move"].create(self._invoice_vals(foreign_currency))
        foreign = foreign.with_context(lang="en_US")
        display = foreign.l10n_ve_report_exchange_rate_display()
        symbol = (foreign.company_currency_id.symbol or "Bs").strip()
        four = formatLang(foreign.env, foreign.l10n_ve_inverse_rate, digits=4)
        two = formatLang(foreign.env, foreign.l10n_ve_inverse_rate, digits=2)
        self.assertEqual(display, f"{four} {symbol}")
        self.assertNotEqual(display, f"{two} {symbol}")
