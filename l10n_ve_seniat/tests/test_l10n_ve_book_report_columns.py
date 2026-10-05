# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest import SkipTest

from odoo.tests import tagged

from odoo.addons.l10n_ve_seniat.tests.common import L10nVeSeniatCommon


@tagged("post_install", "-at_install", "l10n_ve_reports")
class TestL10nVeBookReportColumns(L10nVeSeniatCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        reports_module = cls.env["ir.module.module"].search(
            [("name", "=", "l10n_ve_reports"), ("state", "=", "installed")]
        )
        if not reports_module:
            raise SkipTest("l10n_ve_reports is not installed")
        cls.handler = cls.env["account.sales.book.report.handler.oca"]
        cls.tax_group_model = cls.env["account.tax.group"]
        cls.ve_country = cls.env.ref("base.ve")
        cls.exempt_group = cls._configure_tax_group("exempt", sequence=50)
        cls.general_group = cls._configure_tax_group("general", sequence=20)
        cls.reduced_group = cls._configure_tax_group("reduced", sequence=10)

    @classmethod
    def _configure_tax_group(cls, aliquot_type, sequence):
        group = cls.tax_group_model.search(
            [
                ("company_id", "=", cls.env.company.id),
                ("country_id", "=", cls.ve_country.id),
                ("l10n_ve_aliquot_type", "=", aliquot_type),
            ],
            limit=1,
        )
        values = {
            "sequence": sequence,
            "l10n_ve_exclude_from_reports": False,
            "l10n_ve_aliquot_type": aliquot_type,
        }
        if group:
            group.write(values)
            return group
        return cls.tax_group_model.create(
            {
                "name": f"Grupo {aliquot_type} reporte",
                "company_id": cls.env.company.id,
                "country_id": cls.ve_country.id,
                **values,
            }
        )

    def _sales_book_labels(self):
        report = self.env.ref("l10n_ve_reports.sales_book_report")
        options = report.get_options({})
        return [column.get("expression_label") for column in options["columns"]]

    def test_sales_book_aliquot_columns_follow_tax_group_sequence(self):
        labels = self._sales_book_labels()
        self.assertLess(
            labels.index("tax_base_reduced_aliquot"),
            labels.index("tax_base_general_aliquot"),
        )

    def test_sales_book_exempt_column_keeps_its_position(self):
        labels = self._sales_book_labels()
        exempt_index = labels.index("total_sales_not_iva")
        self.assertEqual(labels[exempt_index - 1], "total_sales_iva")
        self.assertLess(exempt_index, labels.index("tax_base_reduced_aliquot"))
        self.assertLess(exempt_index, labels.index("tax_base_general_aliquot"))
