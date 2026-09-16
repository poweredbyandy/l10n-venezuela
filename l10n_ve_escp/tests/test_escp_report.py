import base64
import json

from odoo import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_ve_escp.report.escp_engine import escapy_available
from odoo.addons.l10n_ve_escp.report.frx_parser import frx_layout


@tagged("post_install", "-at_install")
class TestL10nVeEscpReport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Empresa Prueba",
                "vat": "J123456789",
                "child_ids": [
                    Command.create({"name": "Contacto Uno", "type": "contact"}),
                    Command.create({"name": "Contacto Dos", "type": "contact"}),
                    Command.create({"name": "Contacto Tres", "type": "contact"}),
                ],
            }
        )
        model = cls.env["ir.model"]._get("res.partner")
        cls.report = cls.env["l10n.ve.escp.report"].create(
            {
                "name": "Ficha de contactos",
                "model_id": model.id,
                "cpi": "10",
                "lpi": "6",
                "paper_width_in": 8.0,
                "paper_height_in": 2.0,
                "band_ids": [
                    Command.create(
                        {
                            "band_type": "page_header",
                            "height": 2,
                            "object_ids": [
                                Command.create(
                                    {
                                        "kind": "label",
                                        "row": 0,
                                        "col": 0,
                                        "width": 10,
                                        "text": "Empresa:",
                                        "style": "bold",
                                    }
                                ),
                                Command.create(
                                    {
                                        "kind": "field",
                                        "row": 0,
                                        "col": 10,
                                        "width": 30,
                                        "expr": "upper(o.name)",
                                    }
                                ),
                                Command.create(
                                    {
                                        "kind": "field",
                                        "row": 1,
                                        "col": 60,
                                        "width": 20,
                                        "align": "right",
                                        "expr": "'Pag %s/%s' % (page, page_count)",
                                    }
                                ),
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "band_type": "detail",
                            "height": 1,
                            "detail_rows": 2,
                            "detail_expr": "o.child_ids.sorted('name')",
                            "object_ids": [
                                Command.create(
                                    {
                                        "kind": "field",
                                        "row": 0,
                                        "col": 0,
                                        "width": 4,
                                        "format": "integer",
                                        "expr": "line_no",
                                    }
                                ),
                                Command.create(
                                    {
                                        "kind": "field",
                                        "row": 0,
                                        "col": 5,
                                        "width": 40,
                                        "expr": "line.name",
                                    }
                                ),
                            ],
                        }
                    ),
                    Command.create(
                        {
                            "band_type": "page_footer",
                            "height": 1,
                            "object_ids": [
                                Command.create(
                                    {
                                        "kind": "field",
                                        "row": 0,
                                        "col": 0,
                                        "width": 40,
                                        "style": "bold_wide",
                                        "expr": "'TOTAL %s' % len(o.child_ids)",
                                        "print_when": "page == page_count",
                                    }
                                ),
                            ],
                        }
                    ),
                ],
            }
        )

    def test_pl_reads_record_fields(self):
        detail = self.report.band_ids.filtered(lambda b: b.band_type == "detail")
        detail.object_ids.filtered(lambda o: o.expr == "line.name").write({"expr": "pl.name"})
        pages = self.report._render_pages(self.partner)
        first = pages[0].text_lines()
        self.assertIn("Contacto Dos", first[2])
        self.assertIn("Contacto Tres", first[3])

    def test_field_helper_reads_dotted_paths(self):
        ctx = self.report._base_eval_context(self.partner)
        self.assertEqual(ctx["field"](self.partner, "name"), "Empresa Prueba")
        self.assertEqual(ctx["field"](self.partner, "child_ids.name"), self.partner.child_ids.mapped("name"))

    def test_render_pages_and_bands(self):
        pages = self.report._render_pages(self.partner)
        self.assertEqual(len(pages), 2)
        first = pages[0].text_lines()
        self.assertEqual(len(first), 5)
        self.assertEqual(len(first[0]), 80)
        self.assertTrue(first[0].startswith("Empresa:  EMPRESA PRUEBA"))
        self.assertIn("Pag 1/2", first[1])
        self.assertEqual(first[2][:5].strip(), "1")
        self.assertIn("Contacto Dos", first[2])
        self.assertIn("Contacto Tres", first[3])
        self.assertEqual(first[4].strip(), "")
        last = pages[1].text_lines()
        self.assertIn("Contacto Uno", last[2])
        self.assertIn("T O T A L   3", last[4])

    def test_escp_bytes_and_report_action(self):
        raw = self.report._render_escp(self.partner)
        self.assertTrue(raw.startswith(b"\x1b@"))
        self.assertIn(b"\x1bP", raw)
        self.assertNotIn(b"\x0f", raw)
        self.assertIn(b"\x1bE", raw)
        self.assertIn(b"\x1bW\x01", raw)
        self.assertEqual(raw.count(b"\n\x0c"), 2)
        self.assertIn(b"\x1bC\x0c", raw)
        action = self.report.report_action_id
        self.assertEqual(action.report_type, "escp")
        self.assertEqual(action.model, "res.partner")
        self.assertEqual(action.binding_model_id, self.report.model_id)
        result = action.report_action(self.partner)
        self.assertEqual(result["report_type"], "escp")
        self.assertEqual(result["l10n_ve_escp_report_id"], self.report.id)
        content, kind = action._render(action.report_name, self.partner.ids)
        self.assertEqual(kind, "escp")
        self.assertEqual(content, raw)

    def test_preview_wizard_and_payload(self):
        wizard = (
            self.env["l10n.ve.escp.preview"]
            .with_context(
                default_report_id=self.report.id,
                default_res_ids=json.dumps(self.partner.ids),
            )
            .create({})
        )
        self.assertEqual(wizard.record_count, 1)
        self.assertIn("EMPRESA PRUEBA", wizard.preview_html)
        self.assertIn('<span class="o_escp_b">', wizard.preview_html)
        if escapy_available():
            self.assertTrue(base64.b64decode(wizard.preview_pdf).startswith(b"%PDF"))
        payload = self.env["l10n.ve.escp.report"].get_print_payload(
            self.report.id, "res.partner", json.dumps(self.partner.ids)
        )
        self.assertEqual(base64.b64decode(payload["payload_b64"]), self.report._render_escp(self.partner))
        self.assertTrue(
            self.env["l10n.ve.escp.report"].confirm_printed(
                self.report.id, "res.partner", self.partner.ids
            )
        )

    def test_designer_load_and_save(self):
        self.report.sample_ref = self.partner
        data = self.report.designer_load()
        self.assertEqual(data["report"]["line_width"], 80)
        self.assertEqual(data["report"]["page_rows"], 12)
        self.assertEqual([b["band_type"] for b in data["bands"]], ["page_header", "detail", "page_footer"])
        header = data["bands"][0]
        field = next(o for o in header["objects"] if o["kind"] == "field")
        self.assertEqual(data["sample_values"][field["id"]], "EMPRESA PRUEBA")
        detail = data["bands"][1]
        name_obj = next(o for o in detail["objects"] if o["expr"] == "line.name")
        self.assertEqual(data["sample_values"][name_obj["id"]], "Contacto Dos")
        label = next(o for o in header["objects"] if o["kind"] == "label")
        payload = {
            "bands": [
                {
                    "id": header["id"],
                    "band_type": "page_header",
                    "height": 3,
                    "objects": [
                        {**label, "row": 1, "col": 4, "text": "Cliente:"},
                        {**field, "id": 0, "row": 2, "col": 4, "expr": "o.vat"},
                    ],
                },
                {"id": detail["id"], "band_type": "detail", "height": 1, "detail_rows": 2,
                 "detail_expr": detail["detail_expr"], "objects": detail["objects"]},
                {"id": 0, "band_type": "summary", "height": 1, "objects": [
                    {"kind": "label", "row": 0, "col": 0, "width": 10, "text": "Resumen", "style": "bold"}
                ]},
            ],
            "deleted_object_ids": [o["id"] for o in header["objects"] if o["kind"] == "field"],
            "deleted_band_ids": [data["bands"][2]["id"]],
            "margin_top_lines": 1,
        }
        result = self.report.designer_save(payload)
        self.assertEqual([b["band_type"] for b in result["bands"]], ["page_header", "detail", "summary"])
        self.assertEqual(result["report"]["margin_top_lines"], 1)
        header = result["bands"][0]
        self.assertEqual(header["height"], 3)
        self.assertEqual(sorted(o["kind"] for o in header["objects"]), ["field", "label"])
        self.assertEqual(next(o for o in header["objects"] if o["kind"] == "label")["text"], "Cliente:")
        self.assertEqual(next(o for o in header["objects"] if o["kind"] == "field")["expr"], "o.vat")
        lines = self.report._render_pages(self.partner)[0].text_lines()
        self.assertEqual(lines[1 + 1][4:12], "Cliente:")
        self.assertIn("J123456789", lines[1 + 2])
        self.assertIn("Resumen", "\n".join(self.report._render_pages(self.partner)[-1].text_lines()))
        action = self.report.action_open_designer()
        self.assertEqual(action["tag"], "l10n_ve_escp_designer")
        self.assertEqual(action["params"]["report_id"], self.report.id)

    def test_unlink_removes_action(self):
        action = self.report.report_action_id
        self.report.unlink()
        self.assertFalse(action.exists())

    def test_frx_layout_bands(self):
        records = [
            {"OBJTYPE": 1, "WIDTH": 85000.0},
            {"OBJTYPE": 9, "OBJCODE": 1, "HEIGHT": 25209.0},
            {"OBJTYPE": 9, "OBJCODE": 4, "HEIGHT": 1653.0},
            {"OBJTYPE": 9, "OBJCODE": 7, "HEIGHT": 25209.0},
            {"OBJTYPE": 5, "VPOS": 10937.5, "HPOS": 3229.0, "EXPR": '"Razon Social"'},
            {"OBJTYPE": 8, "VPOS": 27291.6, "HPOS": 2812.5, "EXPR": "codigo"},
            {"OBJTYPE": 8, "VPOS": 46875.0, "HPOS": 62395.8, "EXPR": "totalfinal"},
        ]
        width, bands = frx_layout(records)
        self.assertEqual(width, 85000.0)
        self.assertEqual([b["type"] for b in bands], ["page_header", "detail", "page_footer"])
        self.assertEqual(len(bands[0]["objects"]), 1)
        self.assertEqual(len(bands[1]["objects"]), 1)
        self.assertAlmostEqual(bands[1]["objects"][0]["rel_vpos"], 0.0, places=0)
        self.assertEqual(len(bands[2]["objects"]), 1)
        self.assertAlmostEqual(bands[2]["objects"][0]["rel_vpos"], 15846.0, delta=5)
