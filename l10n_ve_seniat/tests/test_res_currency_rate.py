# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestResCurrencyRate(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")
        cls.today = fields.Date.today()

    def _create_usd_rate(self, inverse_company_rate=40.0):
        rate_model = self.env["res.currency.rate"]
        rate = rate_model.search(
            [
                ("currency_id", "=", self.usd.id),
                ("company_id", "=", self.env.company.id),
                ("name", "=", self.today),
            ],
            limit=1,
        )
        vals = {
            "currency_id": self.usd.id,
            "company_id": self.env.company.id,
            "name": self.today,
            "inverse_company_rate": inverse_company_rate,
            "l10n_ve_rate_edit_count": 0,
        }
        ctx = {"l10n_ve_skip_currency_rate_validation": True}
        if rate:
            rate.with_context(**ctx).write(vals)
            return rate
        return rate_model.with_context(**ctx).create(vals)

    def _create_usd_invoice(self, post=False):
        invoice = self.init_invoice(
            "out_invoice",
            partner=self.partner_a,
            invoice_date=self.today,
            currency=self.usd,
            amounts=[100.0],
            taxes=self.tax_sale_a,
        )
        if post:
            invoice.action_post()
        return invoice

    def test_rate_write_blocked_by_posted_invoice(self):
        rate = self._create_usd_rate()
        invoice = self._create_usd_invoice(post=True)
        self.assertEqual(invoice.currency_id, self.usd)
        posted_moves = rate._l10n_ve_get_posted_moves_using_rate()
        self.assertIn(
            invoice,
            posted_moves,
            "invoice_date=%s rate.name=%s" % (invoice.invoice_date, rate.name),
        )
        self.assertTrue(rate._l10n_ve_company_uses_rate_rules())

        with self.assertRaises(UserError) as error:
            rate.with_context(l10n_ve_skip_currency_rate_validation=False).write(
                {"inverse_company_rate": 45.0}
            )

        self.assertIn("facturas confirmadas", str(error.exception).lower())
        self.assertIn(invoice.name, str(error.exception))

    def test_rate_write_allowed_when_invoice_is_draft(self):
        rate = self._create_usd_rate()
        self._create_usd_invoice(post=False)

        rate.write({"inverse_company_rate": 45.0})
        self.assertEqual(rate.inverse_company_rate, 45.0)

    def test_rate_write_allowed_after_invoice_reset_to_draft(self):
        rate = self._create_usd_rate()
        invoice = self._create_usd_invoice(post=True)
        invoice.with_context(force_draft=True).button_draft()

        rate.write({"inverse_company_rate": 45.0})
        self.assertEqual(rate.inverse_company_rate, 45.0)

    def test_draft_invoice_currency_rate_outdated_alert(self):
        rate = self._create_usd_rate(inverse_company_rate=40.0)
        invoice = self._create_usd_invoice(post=False)
        self.assertFalse(invoice.l10n_ve_currency_rate_outdated)

        rate.write({"inverse_company_rate": 50.0})
        invoice.refresh_invoice_currency_rate()
        invoice.invalidate_recordset(["l10n_ve_currency_rate_outdated"])
        self.assertFalse(invoice.l10n_ve_currency_rate_outdated)
