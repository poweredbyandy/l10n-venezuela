import base64
import json

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_ve_escp.report.escp_engine import escapy_available
from odoo.addons.l10n_ve_invoice_escp.report.invoice_values import line_context
from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install")
class TestL10nVeInvoiceEscp(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env.ref("l10n_ve_invoice_escp.l10n_ve_escp_report_invoice")

    def _invoice(self, name, vat, price=10.0, qty=1.0, lines=1, post=True):
        move = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "invoice_date": fields.Date.today(),
                "partner_id": self.env["res.partner"]
                .create(
                    {
                        "name": name,
                        "country_id": self.env.ref("base.ve").id,
                        "vat": vat,
                    }
                )
                .id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": f"Linea {index + 1}",
                            "quantity": qty,
                            "price_unit": price,
                            "account_id": self.company_data[
                                "default_account_revenue"
                            ].id,
                            "tax_ids": [
                                (6, 0, [self.company_data["default_tax_sale"].id])
                            ],
                        },
                    )
                    for index in range(lines)
                ],
            }
        )
        if post:
            move.action_post()
        return move

    def _configure_continuous_journal(self, detail_rows=35, margin_lines=0):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal, print_medium="continuous")
        journal.l10n_ve_invoice_section_id.book_id.write(
            {
                "l10n_ve_escp_invoice_margin_lines": margin_lines,
                "l10n_ve_max_invoice_lines": detail_rows,
            }
        )
        return journal

    def _text(self, move, report=None):
        report = report or self.report
        pages = report._render_pages(move)
        return pages, ["\n".join(page.text_lines()) for page in pages]

    def test_line_context_company_currency_fields(self):
        move = self._invoice("Cliente moneda", "J12345676")
        line = move.invoice_line_ids.filtered(lambda l: l.display_type == "product")[:1]
        pl = line_context(move, line)["pl"]
        for name in (
            "price_unit_company_currency",
            "price_subtotal_currency",
            "subtotal_company_currency",
        ):
            self.assertTrue(getattr(pl, name), msg=name)

    def test_report_expr_uses_line_fields_directly(self):
        custom = self.report.copy({"name": "Campos directos"})
        detail = custom.band_ids.filtered(lambda b: b.band_type == "detail")
        detail.object_ids.create(
            {
                "band_id": detail.id,
                "kind": "field",
                "row": 0,
                "col": 120,
                "width": 20,
                "expr": "line.price_subtotal_currency",
                "format": "monetary",
                "currency_expr": "comp_currency",
            }
        )
        move = self._invoice("Cliente campos", "J12345677")
        _pages, texts = self._text(move, custom)
        self.assertNotIn("#ERR", texts[0])
        line = move.invoice_line_ids.filtered(lambda l: l.display_type == "product")[:1]
        self.assertIn(str(line.price_subtotal_currency).split(".")[0], texts[0])

    def test_default_report_layout(self):
        self._configure_continuous_journal()
        move = self._invoice("Cliente ESCP", "J12345670")
        pages, texts = self._text(move)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].rows, 66)
        self.assertEqual(pages[0].width, 145)
        text = texts[0]
        for expected in (
            "Razon Social :",
            "Cliente ESCP",
            "R.I.F. :",
            "J12345670",
            "Código",
            "Nombre del artículo",
            "Exento (+):",
            "Total I.V.A. al 16% (+):",
            "TOTAL A PAGAR",
            "Son: ",
        ):
            self.assertIn(expected, text)
        self.assertIn("F A C T U R A", text)
        self.assertNotIn("Nombre y Apellido", text)
        raw = self.report._render_escp(move)
        self.assertIn(b"\x1bE\x1bW\x01FACTURA\x1bF\x1bW\x00", raw)
        self.assertIn(b"\x1bx\x00\x1bG", raw)
        self.assertIn(b"\x1bP\x0f", raw)
        self.assertIn(b"\x1bC" + bytes([66]), raw)

    def test_talonario_overrides_margin_and_detail_rows(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal, print_medium="continuous")
        book = journal.l10n_ve_invoice_section_id.book_id
        book.write(
            {
                "l10n_ve_escp_invoice_margin_lines": 5,
                "l10n_ve_max_invoice_lines": 3,
            }
        )
        move = self._invoice("Cliente talonario", "J12345678", lines=5)
        pages, texts = self._text(move)
        self.assertEqual(len(pages), 2)
        self.assertTrue(all(not line.strip() for line in pages[0].text_lines()[:5]))
        self.assertIn("Linea 3", texts[0])
        self.assertNotIn("Linea 4", texts[0])
        self.assertIn("Linea 4", texts[1])

    def test_multipage_detail(self):
        self._configure_continuous_journal()
        move = self._invoice("Cliente paginas", "J12345671", lines=40)
        pages, texts = self._text(move)
        self.assertEqual(len(pages), 2)
        self.assertIn("Linea 35", texts[0])
        self.assertNotIn("Linea 36", texts[0])
        self.assertIn("Linea 36", texts[1])
        self.assertIn("Página: 002", texts[1])

    def test_print_action_opens_preview_and_marks_printed(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal, print_medium="continuous")
        move = self._invoice("Cliente preview", "J12345672")
        action = move.action_print_pdf()
        self.assertEqual(action.get("res_model"), "l10n.ve.escp.preview")
        self.assertEqual(action["context"]["default_report_id"], self.report.id)
        wizard = (
            self.env["l10n.ve.escp.preview"]
            .with_context(**action["context"])
            .create({})
        )
        self.assertIn("Cliente preview", wizard.preview_html)
        if escapy_available():
            self.assertTrue(base64.b64decode(wizard.preview_pdf).startswith(b"%PDF"))
        print_action = wizard.action_print()
        self.assertEqual(print_action["tag"], "l10n_ve_escp_print")
        self.assertEqual(print_action["params"]["res_ids"], move.ids)
        Report = self.env["l10n.ve.escp.report"]
        payload = Report.get_print_payload(self.report.id, "account.move", json.dumps(move.ids))
        self.assertTrue(payload["payload_b64"])
        self.assertFalse(move.l10n_ve_invoice_original_printed)
        Report.confirm_printed(self.report.id, "account.move", move.ids)
        self.assertTrue(move.l10n_ve_invoice_original_printed)
        _pages, texts = self._text(move)
        self.assertIn("COPIA SIN DERECHO A CREDITO FISCAL", texts[0])

    def test_payload_requires_continuous_journal(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal, print_medium="pdf")
        move = self._invoice("Cliente PDF", "J12345673")
        with self.assertRaises(UserError):
            self.env["l10n.ve.escp.report"].get_print_payload(
                self.report.id, "account.move", move.ids
            )
        self.assertNotEqual(
            move.action_print_pdf().get("res_model"), "l10n.ve.escp.preview"
        )

    def test_draft_invoice_cannot_print(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal, print_medium="continuous")
        move = self._invoice("Cliente borrador", "J12345674", post=False)
        with self.assertRaises(UserError):
            self.env["l10n.ve.escp.report"].get_print_payload(
                self.report.id, "account.move", move.ids
            )

    def test_journal_report_override(self):
        journal = self.company_data["default_journal_sale"]
        self._l10n_ve_configure_journal_free(journal, print_medium="continuous")
        custom = self.report.copy({"name": "Personalizado"})
        custom.band_ids.filtered(lambda b: b.band_type == "page_header").object_ids.filtered(
            lambda o: o.kind == "label" and o.text == "Razon Social :"
        ).write({"text": "Cliente :"})
        journal.l10n_ve_escp_report_id = custom
        move = self._invoice("Cliente custom", "J12345675")
        self.assertEqual(move._l10n_ve_escp_report(), custom)
        _pages, texts = self._text(move, custom)
        self.assertIn("Cliente :", texts[0])
        self.assertNotIn("Razon Social :", texts[0])
        self.assertEqual(move.action_print_pdf()["context"]["default_report_id"], custom.id)
