# Copyright 2026 Anderson Armeya
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestCurrencyRateIndex(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.Currency = cls.env["res.currency"].with_context(active_test=False)
        cls.Rate = cls.env["res.currency.rate"]
        cls.RateIndex = cls.env["res.currency.rate.index"]

        cls.ves = cls.Currency.search([("name", "=", "VES")], limit=1)
        if not cls.ves:
            cls.ves = cls.Currency.create(
                {
                    "name": "VES",
                    "symbol": "Bs",
                    "rounding": 0.01,
                    "position": "before",
                    "currency_unit_label": "Bolivar",
                    "currency_subunit_label": "Centimo",
                }
            )
        cls.ves.active = True

        cls.usd = cls.Currency.search([("name", "=", "USD")], limit=1)
        if not cls.usd:
            cls.usd = cls.Currency.create(
                {
                    "name": "USD",
                    "symbol": "$",
                    "rounding": 0.01,
                    "position": "before",
                    "currency_unit_label": "Dollar",
                    "currency_subunit_label": "Cent",
                }
            )
        cls.usd.active = True

        cls.usdt = cls.Currency.search([("name", "=", "UST")], limit=1)
        if not cls.usdt:
            cls.usdt = cls.Currency.create(
                {
                    "name": "UST",
                    "symbol": "USDT",
                    "rounding": 0.01,
                    "position": "before",
                    "currency_unit_label": "Tether",
                    "currency_subunit_label": "Cent",
                }
            )
        cls.usdt.active = True

        cls.yen = cls.Currency.search([("name", "=", "JPY")], limit=1)
        if not cls.yen:
            cls.yen = cls.Currency.create(
                {
                    "name": "JPY",
                    "symbol": "¥",
                    "rounding": 1.0,
                    "position": "before",
                    "currency_unit_label": "Yen",
                    "currency_subunit_label": "Sen",
                }
            )
        cls.yen.active = True

        cls.cny = cls.Currency.search([("name", "=", "CNY")], limit=1)
        if not cls.cny:
            cls.cny = cls.Currency.create(
                {
                    "name": "CNY",
                    "symbol": "¥",
                    "rounding": 0.01,
                    "position": "before",
                    "currency_unit_label": "Yuan",
                    "currency_subunit_label": "Fen",
                }
            )
        cls.cny.active = True

        cls.company.currency_id = cls.ves
        cls.company.currency_index_id = cls.usd

        cls.date = fields.Date.to_date("2026-01-15")
        cls.date_old = fields.Date.to_date("2026-01-01")
        cls.date_new = fields.Date.to_date("2026-02-01")

        cls.Rate.search(
            [
                ("currency_id", "in", (cls.usd | cls.usdt | cls.yen | cls.cny).ids),
                ("company_id", "in", (False, cls.company.root_id.id)),
            ]
        ).unlink()
        cls.RateIndex.search(
            [
                ("currency_id", "in", (cls.usd | cls.usdt | cls.yen | cls.cny).ids),
                ("company_id", "in", (False, cls.company.root_id.id)),
            ]
        ).unlink()

        cls.Rate.create(
            [
                {
                    "name": cls.date_old,
                    "currency_id": cls.usd.id,
                    "company_id": cls.company.root_id.id,
                    "rate": 1.0 / 876.0,
                },
                {
                    "name": cls.date_old,
                    "currency_id": cls.usdt.id,
                    "company_id": cls.company.root_id.id,
                    "rate": 1.0 / 1000.0,
                },
                {
                    "name": cls.date_old,
                    "currency_id": cls.yen.id,
                    "company_id": cls.company.root_id.id,
                    "rate": 1.0 / 6.0,
                },
            ]
        )
        cls.RateIndex.create(
            [
                {
                    "name": cls.date_old,
                    "currency_id": cls.usdt.id,
                    "company_id": cls.company.root_id.id,
                    "rate": 1.0,
                },
                {
                    "name": cls.date_old,
                    "currency_id": cls.yen.id,
                    "company_id": cls.company.root_id.id,
                    "rate": 0.0067,
                },
                {
                    "name": cls.date_old,
                    "currency_id": cls.cny.id,
                    "company_id": cls.company.root_id.id,
                    "rate": 0.14,
                },
            ]
        )

    def test_usdt_to_usd_uses_index_rate(self):
        amount = self.usdt._convert(100.0, self.usd, self.company, self.date)
        self.assertEqual(amount, 100.0)

    def test_usd_to_usdt_uses_index_rate(self):
        amount = self.usd._convert(100.0, self.usdt, self.company, self.date)
        self.assertEqual(amount, 100.0)

    def test_yen_to_usdt_via_index(self):
        amount = self.yen._convert(1000.0, self.usdt, self.company, self.date)
        self.assertAlmostEqual(amount, 6.7, places=2)

    def test_yen_to_usd_uses_index_rate(self):
        amount = self.yen._convert(1000.0, self.usd, self.company, self.date)
        self.assertAlmostEqual(amount, 6.7, places=2)

    def test_ves_conversions_remain_native(self):
        usd_to_ves = self.usd._convert(1.0, self.ves, self.company, self.date)
        usdt_to_ves = self.usdt._convert(1.0, self.ves, self.company, self.date)
        ves_to_usd = self.ves._convert(876.0, self.usd, self.company, self.date)
        self.assertAlmostEqual(usd_to_ves, 876.0, places=2)
        self.assertAlmostEqual(usdt_to_ves, 1000.0, places=2)
        self.assertAlmostEqual(ves_to_usd, 1.0, places=2)

    def test_fallback_without_index_currency(self):
        self.company.currency_index_id = False
        amount = self.usdt._convert(100.0, self.usd, self.company, self.date)
        expected = 100.0 * (1000.0 / 876.0)
        self.assertAlmostEqual(amount, expected, places=2)

    def test_fallback_without_index_rate(self):
        self.RateIndex.search([("currency_id", "=", self.usdt.id)]).unlink()
        amount = self.usdt._convert(100.0, self.usd, self.company, self.date)
        expected = 100.0 * (1000.0 / 876.0)
        self.assertAlmostEqual(amount, expected, places=2)

    def test_index_rate_by_date(self):
        self.RateIndex.create(
            {
                "name": self.date_new,
                "currency_id": self.usdt.id,
                "company_id": self.company.root_id.id,
                "rate": 0.9,
            }
        )
        before = self.usdt._convert(100.0, self.usd, self.company, self.date)
        after = self.usdt._convert(100.0, self.usd, self.company, self.date_new)
        self.assertEqual(before, 100.0)
        self.assertEqual(after, 90.0)

    def test_no_fallback_to_oldest_index_rate(self):
        self.RateIndex.search([("currency_id", "=", self.usdt.id)]).unlink()
        self.RateIndex.create(
            {
                "name": self.date_new,
                "currency_id": self.usdt.id,
                "company_id": self.company.root_id.id,
                "rate": 1.0,
            }
        )
        amount = self.usdt._convert(100.0, self.usd, self.company, self.date)
        expected = 100.0 * (1000.0 / 876.0)
        self.assertAlmostEqual(amount, expected, places=2)

    def test_currency_index_cannot_be_company_currency(self):
        with self.assertRaises(ValidationError):
            self.company.currency_index_id = self.ves

    def test_index_rate_must_be_positive(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self.RateIndex.create(
                {
                    "name": self.date,
                    "currency_id": self.usdt.id,
                    "company_id": self.company.root_id.id,
                    "rate": 0.0,
                }
            )

    def test_inverse_rate_mirrors_rate(self):
        rate = self.RateIndex.search(
            [("currency_id", "=", self.yen.id)], limit=1
        )
        self.assertAlmostEqual(rate.rate, 0.0067, places=6)
        self.assertAlmostEqual(rate.inverse_rate, 1.0 / 0.0067, places=4)

    def test_create_with_inverse_rate(self):
        rate = self.RateIndex.create(
            {
                "name": self.date,
                "currency_id": self.usdt.id,
                "company_id": self.company.root_id.id,
                "inverse_rate": 2.0,
            }
        )
        self.assertAlmostEqual(rate.rate, 0.5, places=6)
        self.assertAlmostEqual(rate.inverse_rate, 2.0, places=6)
        amount = self.usdt._convert(100.0, self.usd, self.company, self.date)
        self.assertEqual(amount, 50.0)

    def test_write_inverse_rate_updates_rate(self):
        rate = self.RateIndex.search(
            [("currency_id", "=", self.usdt.id)], limit=1
        )
        rate.inverse_rate = 1.25
        self.assertAlmostEqual(rate.rate, 0.8, places=6)
        amount = self.usdt._convert(100.0, self.usd, self.company, self.date)
        self.assertEqual(amount, 80.0)

    def test_cny_to_ves_via_usd_index(self):
        self.Rate.search([("currency_id", "=", self.cny.id)]).unlink()
        amount = self.cny._convert(100.0, self.ves, self.company, self.date)
        expected = 100.0 * 0.14 * 876.0
        self.assertAlmostEqual(amount, expected, places=2)

    def test_ves_to_cny_via_usd_index(self):
        self.Rate.search([("currency_id", "=", self.cny.id)]).unlink()
        ves_amount = 100.0 * 0.14 * 876.0
        amount = self.ves._convert(ves_amount, self.cny, self.company, self.date)
        self.assertAlmostEqual(amount, 100.0, places=2)

    def test_cny_to_ves_uses_native_when_present(self):
        self.Rate.search([("currency_id", "=", self.cny.id)]).unlink()
        self.Rate.create(
            {
                "name": self.date_old,
                "currency_id": self.cny.id,
                "company_id": self.company.root_id.id,
                "rate": 1.0 / 50.0,
            }
        )
        amount = self.cny._convert(1.0, self.ves, self.company, self.date)
        self.assertAlmostEqual(amount, 50.0, places=2)

    def test_index_rate_creates_native_ves_rate(self):
        self.Rate.search([("currency_id", "=", self.cny.id)]).unlink()
        self.RateIndex.search([("currency_id", "=", self.cny.id)]).unlink()
        self.RateIndex.create(
            {
                "name": self.date,
                "currency_id": self.cny.id,
                "company_id": self.company.root_id.id,
                "rate": 0.14,
            }
        )
        native = self.Rate.search(
            [
                ("currency_id", "=", self.cny.id),
                ("name", "=", self.date),
                ("company_id", "=", self.company.root_id.id),
            ],
            limit=1,
        )
        self.assertTrue(native)
        self.assertTrue(native.rate_index_synced)
        self.assertAlmostEqual(native.inverse_company_rate, 0.14 * 876.0, places=4)
        amount = self.cny._convert(100.0, self.ves, self.company, self.date)
        self.assertAlmostEqual(amount, 100.0 * 0.14 * 876.0, places=2)

    def test_index_rate_requires_index_currency(self):
        self.company.currency_index_id = False
        with self.assertRaises(ValidationError):
            self.RateIndex.create(
                {
                    "name": self.date,
                    "currency_id": self.cny.id,
                    "company_id": self.company.root_id.id,
                    "rate": 0.14,
                }
            )

    def test_setting_index_currency_syncs_existing_index_rates(self):
        self.RateIndex.search([("currency_id", "=", self.cny.id)]).unlink()
        self.RateIndex.create(
            {
                "name": self.date,
                "currency_id": self.cny.id,
                "company_id": self.company.root_id.id,
                "rate": 0.14,
            }
        )
        self.Rate.search([("currency_id", "=", self.cny.id)]).unlink()
        self.company.currency_index_id = False
        self.company.currency_index_id = self.usd
        native = self.Rate.search(
            [
                ("currency_id", "=", self.cny.id),
                ("name", "=", self.date),
                ("company_id", "=", self.company.root_id.id),
            ]
        )
        self.assertTrue(native.rate_index_synced)
        self.assertAlmostEqual(native.inverse_company_rate, 0.14 * 876.0, places=4)

    def test_index_rate_updates_synced_native_rate(self):
        self.Rate.search([("currency_id", "=", self.cny.id)]).unlink()
        self.RateIndex.search([("currency_id", "=", self.cny.id)]).unlink()
        index_rate = self.RateIndex.create(
            {
                "name": self.date,
                "currency_id": self.cny.id,
                "company_id": self.company.root_id.id,
                "rate": 0.14,
            }
        )
        index_rate.rate = 0.2
        native = self.Rate.search(
            [
                ("currency_id", "=", self.cny.id),
                ("name", "=", self.date),
            ],
            limit=1,
        )
        self.assertAlmostEqual(native.inverse_company_rate, 0.2 * 876.0, places=4)

    def test_index_rate_does_not_overwrite_manual_native_rate(self):
        self.Rate.search([("currency_id", "=", self.usdt.id)]).unlink()
        self.Rate.create(
            {
                "name": self.date_old,
                "currency_id": self.usdt.id,
                "company_id": self.company.root_id.id,
                "rate": 1.0 / 1000.0,
            }
        )
        self.RateIndex.search([("currency_id", "=", self.usdt.id)]).unlink()
        self.RateIndex.create(
            {
                "name": self.date,
                "currency_id": self.usdt.id,
                "company_id": self.company.root_id.id,
                "rate": 1.0,
            }
        )
        native_old = self.Rate.search(
            [
                ("currency_id", "=", self.usdt.id),
                ("name", "=", self.date_old),
            ],
            limit=1,
        )
        native_new = self.Rate.search(
            [
                ("currency_id", "=", self.usdt.id),
                ("name", "=", self.date),
            ],
            limit=1,
        )
        self.assertTrue(native_old)
        self.assertFalse(native_old.rate_index_synced)
        self.assertFalse(native_new)
        self.assertAlmostEqual(
            self.usdt._convert(1.0, self.ves, self.company, self.date),
            1000.0,
            places=2,
        )

    def test_usd_rate_change_updates_synced_cny_rate(self):
        self.Rate.search([("currency_id", "=", self.cny.id)]).unlink()
        self.RateIndex.search([("currency_id", "=", self.cny.id)]).unlink()
        self.RateIndex.create(
            {
                "name": self.date,
                "currency_id": self.cny.id,
                "company_id": self.company.root_id.id,
                "rate": 0.14,
            }
        )
        self.Rate.search(
            [
                ("currency_id", "=", self.usd.id),
                ("name", "=", self.date),
            ]
        ).unlink()
        self.Rate.create(
            {
                "name": self.date,
                "currency_id": self.usd.id,
                "company_id": self.company.root_id.id,
                "rate": 1.0 / 900.0,
            }
        )
        native = self.Rate.search(
            [
                ("currency_id", "=", self.cny.id),
                ("name", "=", self.date),
            ],
            limit=1,
        )
        self.assertAlmostEqual(native.inverse_company_rate, 0.14 * 900.0, places=4)

    def test_purchase_order_currency_rate_refreshes_on_line_write(self):
        self.Rate.search([("currency_id", "=", self.cny.id)]).unlink()
        self.RateIndex.search([("currency_id", "=", self.cny.id)]).unlink()
        self.RateIndex.create(
            {
                "name": self.date,
                "currency_id": self.cny.id,
                "company_id": self.company.root_id.id,
                "rate": 0.14,
            }
        )
        partner = self.env["res.partner"].create({"name": "CNY Vendor"})
        product = self.env["product.product"].create(
            {
                "name": "CNY Product",
                "type": "consu",
                "purchase_ok": True,
                "list_price": 100.0,
                "standard_price": 100.0,
            }
        )
        order = self.env["purchase.order"].create(
            {
                "partner_id": partner.id,
                "currency_id": self.cny.id,
                "date_order": "%s 10:00:00" % self.date,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "name": "Line",
                            "product_id": product.id,
                            "product_qty": 1.0,
                            "price_unit": 100.0,
                            "product_uom": product.uom_id.id,
                            "date_planned": "%s 10:00:00" % self.date,
                        },
                    )
                ],
            }
        )
        order.currency_rate = 1.0
        order.write(
            {
                "order_line": [
                    (1, order.order_line.id, {"price_unit": 110.0}),
                ]
            }
        )
        expected = self.env["res.currency"]._get_conversion_rate(
            self.ves, self.cny, self.company, self.date
        )
        self.assertAlmostEqual(order.currency_rate, expected, places=6)

