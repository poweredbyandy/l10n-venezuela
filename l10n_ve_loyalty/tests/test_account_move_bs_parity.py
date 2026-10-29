# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.tests import Form, tagged
from odoo.tools import float_round

from odoo.addons.l10n_ve_loyalty.tests.common import L10nVeLoyaltyCommon


@tagged("post_install", "-at_install")
class TestAccountMoveBsParity(L10nVeLoyaltyCommon):
    """USD invoices must produce the same Bs amounts as an equivalent VES invoice."""

    INVERSE_RATE = 887.302

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.ves = cls.env.ref("base.VES")
        cls.usd = cls.env.ref("base.USD")
        cls.ves.active = True
        cls.usd.active = True
        cls.env.company.currency_id = cls.ves
        cls.company_data["default_journal_sale"].currency_id = False
        cls.env["res.currency.rate"].search(
            [
                ("currency_id", "=", cls.usd.id),
                ("company_id", "=", cls.env.company.id),
            ]
        ).unlink()
        cls.env["res.currency.rate"].create(
            {
                "currency_id": cls.usd.id,
                "company_id": cls.env.company.id,
                "name": "2026-01-01",
                "inverse_company_rate": cls.INVERSE_RATE,
            }
        )
        cls.partner_ve = cls.env["res.partner"].create(
            {
                "name": "Partner VE Bs parity",
                "country_id": cls.env.ref("base.ve").id,
                "vat": "J123456781",
            }
        )
        cls.discount_allocation_account = cls.env["account.account"].create(
            {
                "name": "VE Global discount allocation parity",
                "code": "VEDISPAR",
                "account_type": "expense",
                "company_ids": [(6, 0, cls.env.company.ids)],
            }
        )
        cls.env.company.account_discount_expense_allocation_id = (
            cls.discount_allocation_account
        )
        cls.payment_term = cls.env.ref("account.account_payment_term_immediate")
        cls.price_prec = cls.env["decimal.precision"].precision_get("Product Price")
        cls.line_defs = (
            ("First product", 16.5, 2.0),
            ("Second product", 37.91, 2.0),
            ("Third product", 1.95, 10.0),
            ("Fractional product", 4.64, 1.5),
        )

    def _pu_bs(self, price_unit_usd):
        return float_round(
            price_unit_usd * self.INVERSE_RATE, precision_digits=self.price_prec
        )

    def _get_discount_reason(self, name):
        reason = self.env["l10n.ve.discount.reason"].search(
            [("name", "=", name)], limit=1
        )
        if not reason:
            reason = self.env["l10n.ve.discount.reason"].create({"name": name})
        return reason

    def _create_parity_invoices(self):
        sale_tax = self.company_data["default_tax_sale"]
        revenue = self.company_data["default_account_revenue"]
        products = []
        for name, price_usd, _qty in self.line_defs:
            products.append(
                self._create_product(
                    name=name,
                    list_price=price_usd,
                    taxes_id=[Command.set(sale_tax.ids)],
                )
            )

        def _lines(currency_is_usd):
            commands = []
            for (name, price_usd, qty), product in zip(
                self.line_defs, products, strict=True
            ):
                price_unit = price_usd if currency_is_usd else self._pu_bs(price_usd)
                commands.append(
                    Command.create(
                        {
                            "product_id": product.id,
                            "name": name,
                            "quantity": qty,
                            "price_unit": price_unit,
                            "account_id": revenue.id,
                            "tax_ids": [Command.set(sale_tax.ids)],
                        }
                    )
                )
            return commands

        common = {
            "move_type": "out_invoice",
            "partner_id": self.partner_ve.id,
            "invoice_date": fields.Date.from_string("2026-01-15"),
            "invoice_payment_term_id": self.payment_term.id,
        }
        move_usd = self.env["account.move"].create(
            {
                **common,
                "currency_id": self.usd.id,
                "invoice_line_ids": _lines(True),
            }
        )
        move_bs = self.env["account.move"].create(
            {
                **common,
                "currency_id": self.ves.id,
                "invoice_line_ids": _lines(False),
            }
        )
        return move_usd, move_bs

    def _add_percentage_discount(self, move, percentage=0.1):
        return self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move.id,
                "reason_id": self._get_discount_reason("Descuento %").id,
                "amount": 1.0,
                "discount_type": "percentage",
                "discount_percentage": percentage,
            }
        )

    def _add_fixed_discount(self, move_usd, move_bs, amount_usd=5.0):
        reason = self._get_discount_reason("Descuento fijo")
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move_usd.id,
                "reason_id": reason.id,
                "amount": amount_usd,
                "discount_type": "fixed",
            }
        )
        amount_bs = self.env.company.currency_id.round(
            float_round(
                amount_usd * self.INVERSE_RATE, precision_digits=self.price_prec
            )
        )
        self.env["l10n.ve.account.move.discount"].create(
            {
                "move_id": move_bs.id,
                "reason_id": reason.id,
                "amount": amount_bs,
                "discount_type": "fixed",
            }
        )

    def _balances_by_display(self, move):
        result = {}
        for display_type in ("product", "tax", "payment_term", "global_discount"):
            lines = move.line_ids.filtered(
                lambda line, display=display_type: line.display_type == display
            )
            if display_type == "global_discount":
                lines = move.line_ids.filtered("l10n_ve_global_discount_line")
            result[display_type] = [
                abs(self.env.company.currency_id.round(line.balance))
                for line in lines.sorted(
                    key=lambda line: (line.name or "", line.id)
                )
            ]
            result[f"{display_type}_sum"] = abs(
                self.env.company.currency_id.round(sum(lines.mapped("balance")))
            )
        return result

    def _assert_bs_parity(self, move_usd, move_bs):
        company_currency = self.env.company.currency_id
        usd_balances = self._balances_by_display(move_usd)
        bs_balances = self._balances_by_display(move_bs)

        self.assertEqual(
            len(usd_balances["product"]),
            len(bs_balances["product"]),
            "Product line count must match",
        )
        for usd_bal, bs_bal in zip(
            usd_balances["product"], bs_balances["product"], strict=True
        ):
            self.assertAlmostEqual(usd_bal, bs_bal, places=2)

        for key in ("tax_sum", "payment_term_sum", "global_discount_sum"):
            self.assertAlmostEqual(
                usd_balances[key],
                bs_balances[key],
                places=2,
                msg=f"Mismatch on {key}",
            )

        self.assertAlmostEqual(
            sum(move_usd.line_ids.mapped("balance")), 0.0, places=2
        )
        self.assertAlmostEqual(
            sum(move_bs.line_ids.mapped("balance")), 0.0, places=2
        )

        usd_totals = move_usd.tax_totals or {}
        bs_totals = move_bs.tax_totals or {}
        accounting = {
            "base_amount": abs(
                company_currency.round(
                    sum(
                        move_usd.line_ids.filtered(
                            lambda line: line.display_type == "product"
                        ).mapped("balance")
                    )
                    + sum(
                        move_usd.line_ids.filtered(
                            "l10n_ve_global_discount_line"
                        ).mapped("balance")
                    )
                )
            ),
            "tax_amount": usd_balances["tax_sum"],
            "total_amount": usd_balances["payment_term_sum"],
        }
        for key in ("base_amount", "tax_amount", "total_amount"):
            self.assertAlmostEqual(
                usd_totals.get(key) or 0.0,
                bs_totals.get(key) or 0.0,
                places=2,
                msg=f"tax_totals.{key} mismatch",
            )
            self.assertAlmostEqual(
                usd_totals.get(key) or 0.0,
                accounting[key],
                places=2,
                msg=f"USD tax_totals.{key} must match accounting",
            )

        if move_usd.l10n_ve_global_discount_ids or usd_totals.get(
            "l10n_ve_show_global_discount"
        ):
            for key in (
                "l10n_ve_subtotal_gross",
                "l10n_ve_global_discount_amount",
            ):
                self.assertAlmostEqual(
                    usd_totals.get(key) or 0.0,
                    bs_totals.get(key) or 0.0,
                    places=2,
                    msg=f"tax_totals.{key} mismatch",
                )

    def test_parity_without_discount(self):
        move_usd, move_bs = self._create_parity_invoices()
        self._assert_bs_parity(move_usd, move_bs)

    def test_parity_with_percentage_discount(self):
        move_usd, move_bs = self._create_parity_invoices()
        self._add_percentage_discount(move_usd, 0.1)
        self._add_percentage_discount(move_bs, 0.1)
        self._assert_bs_parity(move_usd, move_bs)

    def test_parity_with_fixed_discount(self):
        move_usd, move_bs = self._create_parity_invoices()
        self._add_fixed_discount(move_usd, move_bs, 5.0)
        self._assert_bs_parity(move_usd, move_bs)

    def test_parity_form_remove_line_with_percentage_discount(self):
        move_usd, move_bs = self._create_parity_invoices()
        self._add_percentage_discount(move_usd, 0.1)
        self._add_percentage_discount(move_bs, 0.1)

        for move in (move_usd, move_bs):
            move_form = Form(move)
            move_form.invoice_line_ids.remove(index=1)
            move_form.save()

        self._assert_bs_parity(move_usd, move_bs)

    def test_parity_form_edit_quantity_with_percentage_discount(self):
        move_usd, move_bs = self._create_parity_invoices()
        self._add_percentage_discount(move_usd, 0.1)
        self._add_percentage_discount(move_bs, 0.1)

        for move in (move_usd, move_bs):
            move_form = Form(move)
            with move_form.invoice_line_ids.edit(0) as line_form:
                line_form.quantity = 3.0
            move_form.save()

        self._assert_bs_parity(move_usd, move_bs)
