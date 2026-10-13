from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestL10nVeBase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.third_party = cls.env["res.partner"].create({"name": "Tercero"})

    def _new_move(self, move_type):
        return self.env["account.move"].new(
            {
                "move_type": move_type,
                "l10n_ve_third_party_partner_id": self.third_party.id,
            }
        )

    def test_on_behalf_of_third_party_only_for_customer_documents(self):
        for move_type in ("out_invoice", "out_refund"):
            self.assertTrue(self._new_move(move_type).l10n_ve_on_behalf_of_third_party)
        for move_type in ("in_invoice", "in_refund", "entry"):
            self.assertFalse(self._new_move(move_type).l10n_ve_on_behalf_of_third_party)

    def test_on_behalf_of_third_party_requires_partner(self):
        move = self.env["account.move"].new({"move_type": "out_invoice"})
        self.assertFalse(move.l10n_ve_on_behalf_of_third_party)

    def test_company_taxpayer_type_follows_partner(self):
        company = self.env.company
        company.taxpayer_type = "special"
        self.assertEqual(company.partner_id.taxpayer_type, "special")
        company.partner_id.taxpayer_type = "formal"
        self.assertEqual(company.taxpayer_type, "formal")

    def test_aliquot_types(self):
        selection = dict(
            self.env["account.tax.group"]._fields["l10n_ve_aliquot_type"].selection
        )
        self.assertEqual(set(selection), {"exempt", "general", "reduced", "extend"})

    def test_views_show_fields(self):
        expected = {
            "account.view_move_form": [
                "l10n_ve_invoice_date",
                "l10n_ve_control_number",
                "l10n_ve_serial_number",
                "l10n_ve_invoice_number",
                "l10n_ve_report_z",
                "l10n_ve_third_party_partner_id",
                "l10n_ve_journal_emission_medium",
            ],
            "account.view_invoice_tree": [
                "l10n_ve_control_number",
                "l10n_ve_invoice_date",
                "l10n_ve_journal_emission_medium",
            ],
            "account.view_tax_group_form": ["l10n_ve_aliquot_type"],
            "account.view_tax_group_tree": ["l10n_ve_aliquot_type"],
            "base.view_partner_form": ["taxpayer_type"],
            "base.view_company_form": ["taxpayer_type"],
            "account.view_account_journal_form": ["l10n_ve_emission_medium"],
        }
        for xmlid, field_names in expected.items():
            view = self.env.ref(xmlid)
            arch = self.env[view.model].get_view(view.id, view.type)["arch"]
            for field_name in field_names:
                self.assertIn(f'name="{field_name}"', arch, (xmlid, field_name))

    def test_fields_belong_to_base(self):
        fields_data = self.env["ir.model.data"].search(
            [
                ("model", "=", "ir.model.fields"),
                (
                    "name",
                    "in",
                    [
                        "field_account_journal__l10n_ve_emission_medium",
                        "field_account_move__l10n_ve_control_number",
                        "field_account_tax_group__l10n_ve_aliquot_type",
                        "field_res_partner__taxpayer_type",
                    ],
                ),
            ]
        )
        self.assertEqual(set(fields_data.mapped("module")), {"l10n_ve_base"})

    def test_journal_emission_medium_follows_journal(self):
        journal = self.env["account.journal"].create(
            {
                "name": "Ventas contingencia",
                "code": "VCTB",
                "type": "sale",
                "l10n_ve_emission_medium": "contingency",
            }
        )
        move = self.env["account.move"].new(
            {"move_type": "out_invoice", "journal_id": journal.id}
        )
        self.assertEqual(move.l10n_ve_journal_emission_medium, "contingency")

    def test_fiscal_machine_block_depends_on_journal(self):
        view = self.env.ref("account.view_move_form")
        arch = self.env["account.move"].get_view(view.id, "form")["arch"]
        self.assertIn("l10n_ve_journal_emission_medium != 'fiscal_machine'", arch)

    def test_control_number_hidden_without_journal_medium(self):
        self.env.company.country_id = self.env.ref("base.ve")
        journal = self.env["account.journal"].create(
            {"name": "Ventas sin medio", "code": "VSMB", "type": "sale"}
        )
        move = self.env["account.move"].create(
            {"move_type": "out_invoice", "journal_id": journal.id}
        )
        self.assertTrue(Form(move)._get_modifier("l10n_ve_control_number", "invisible"))
        journal.l10n_ve_emission_medium = "contingency"
        self.assertFalse(
            Form(move)._get_modifier("l10n_ve_control_number", "invisible")
        )
        bill = self.env["account.move"].create({"move_type": "in_invoice"})
        self.assertFalse(
            Form(bill)._get_modifier("l10n_ve_control_number", "invisible")
        )
