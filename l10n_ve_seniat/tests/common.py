# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, fields
from odoo.tests import Form

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
        cls._ensure_ve_exent_company_taxes()
        cls._ensure_sale_discount_product()

    @classmethod
    def _ensure_sale_discount_product(cls):
        company = cls.env.company
        if "sale_discount_product_id" not in company._fields:
            return
        if company.sale_discount_product_id:
            return
        product = (
            cls.env["product.template"]
            .with_context(l10n_ve_skip_auto_exent_taxes=True)
            .create(
                {
                    "name": "Descuento SENIAT test",
                    "type": "service",
                    "list_price": 0.0,
                    "taxes_id": [(6, 0, [cls.company_data["default_tax_sale"].id])],
                    "supplier_taxes_id": [
                        (6, 0, [cls.company_data["default_tax_purchase"].id])
                    ],
                }
            )
        )
        company.sale_discount_product_id = product.product_variant_id

    @classmethod
    def _ensure_ve_exent_company_taxes(cls):
        company = cls.env.company
        Tax = cls.env["account.tax"]
        sale_exent = Tax.search(
            [
                ("company_id", "=", company.id),
                ("type_tax_use", "=", "sale"),
                ("amount", "=", 0.0),
            ],
            limit=1,
        )
        purchase_exent = Tax.search(
            [
                ("company_id", "=", company.id),
                ("type_tax_use", "=", "purchase"),
                ("amount", "=", 0.0),
            ],
            limit=1,
        )
        if sale_exent:
            company.exent_aliquot_sale = sale_exent
        else:
            sale_exent = Tax.create(
                {
                    "name": "IVA exento venta test",
                    "amount": 0.0,
                    "amount_type": "percent",
                    "type_tax_use": "sale",
                    "company_id": company.id,
                }
            )
            company.exent_aliquot_sale = sale_exent
        if purchase_exent:
            company.exent_aliquot_purchase = purchase_exent
        else:
            purchase_exent = Tax.create(
                {
                    "name": "IVA exento compra test",
                    "amount": 0.0,
                    "amount_type": "percent",
                    "type_tax_use": "purchase",
                    "company_id": company.id,
                }
            )
            company.exent_aliquot_purchase = purchase_exent

    @classmethod
    def init_invoice(
        cls,
        move_type,
        partner=None,
        invoice_date=None,
        post=False,
        products=None,
        amounts=None,
        taxes=None,
        company=False,
        currency=None,
        journal=None,
    ):
        invoice_date = invoice_date or fields.Date.from_string("2019-01-01")
        company = company or cls.env.company
        products = [] if products is None else products
        amounts = [] if amounts is None else amounts

        move_form = Form(
            cls.env["account.move"]
            .with_company(company)
            .with_context(default_move_type=move_type)
        )
        if not move_form._get_modifier("invoice_date", "invisible"):
            move_form.invoice_date = invoice_date
        if not move_form._get_modifier("date", "invisible"):
            move_form.date = invoice_date
        move_form.partner_id = partner or cls.partner_a
        if journal:
            move_form.journal_id = journal
        if currency and not move_form._get_modifier("currency_id", "invisible"):
            move_form.currency_id = currency

        for product in products or []:
            with move_form.invoice_line_ids.new() as line_form:
                line_form.product_id = product
                if taxes is not None and not line_form._get_modifier(
                    "tax_ids", "readonly"
                ):
                    line_form.tax_ids.clear()
                    for tax in taxes:
                        line_form.tax_ids.add(tax)

        for amount in amounts or []:
            with move_form.invoice_line_ids.new() as line_form:
                line_form.name = "test line"
                line_form.price_unit = amount
                if taxes is not None and not line_form._get_modifier(
                    "tax_ids", "readonly"
                ):
                    line_form.tax_ids.clear()
                    for tax in taxes:
                        line_form.tax_ids.add(tax)

        move = move_form.save()
        if currency and move_form._get_modifier("currency_id", "invisible"):
            move.currency_id = currency
        if invoice_date:
            move.invoice_date = invoice_date
            if not move_form._get_modifier("date", "invisible"):
                move.date = invoice_date
        if taxes is not None:
            tax_ids = [tax.id for tax in taxes]
            for line in move.invoice_line_ids.filtered(
                lambda aml: aml.display_type == "product"
            ):
                if set(line.tax_ids.ids) != set(tax_ids):
                    line.write({"tax_ids": [Command.set(tax_ids)]})

        if post:
            move.action_post()

        return move

    @classmethod
    def _mark_invoice_printed(cls, move):
        move.l10n_ve_invoice_original_printed = True

    @classmethod
    def _create_currency_rate(cls, currency, rate_date, inverse_company_rate):
        return (
            cls.env["res.currency.rate"]
            .with_context(l10n_ve_allow_historical_rate_write=True)
            .create(
                {
                    "currency_id": currency.id,
                    "company_id": cls.env.company.id,
                    "name": rate_date,
                    "inverse_company_rate": inverse_company_rate,
                }
            )
        )

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
