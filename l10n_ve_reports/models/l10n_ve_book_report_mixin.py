from odoo import fields, models


class L10nVeBookReportMixin(models.AbstractModel):
    _name = "l10n.ve.book.report.mixin"
    _description = "Mixin for SENIAT sales and purchase book reports"

    _SALE_ALIQUOT_COLUMNS = {
        "exempt": ["total_sales_not_iva"],
        "general": [
            "tax_base_general_aliquot",
            "general_aliquot",
            "amount_general_aliquot",
        ],
        "reduced": [
            "tax_base_reduced_aliquot",
            "reduced_aliquot",
            "amount_reduced_aliquot",
        ],
        "extend": [
            "tax_base_extend_aliquot",
            "extend_aliquot",
            "amount_extend_aliquot",
        ],
    }

    _SALE_THIRD_PARTY_ALIQUOT_COLUMNS = {
        "general": [
            "third_party_tax_base_general_aliquot",
            "third_party_general_aliquot",
            "third_party_amount_general_aliquot",
        ],
        "reduced": [
            "third_party_tax_base_reduced_aliquot",
            "third_party_reduced_aliquot",
            "third_party_amount_reduced_aliquot",
        ],
        "extend": [
            "third_party_tax_base_extend_aliquot",
            "third_party_extend_aliquot",
            "third_party_amount_extend_aliquot",
        ],
    }

    _PURCHASE_ALIQUOT_COLUMNS = {
        "exempt": ["total_purchases_not_iva"],
        "general": [
            "tax_base_general_aliquot",
            "general_aliquot",
            "amount_general_aliquot",
        ],
        "reduced": [
            "tax_base_reduced_aliquot",
            "reduced_aliquot",
            "amount_reduced_aliquot",
        ],
        "extend": [
            "tax_base_extend_aliquot",
            "extend_aliquot",
            "amount_extend_aliquot",
        ],
    }

    def _l10n_ve_get_aliquot_column_map(self, book_type):
        if book_type == "purchase":
            return self._PURCHASE_ALIQUOT_COLUMNS
        return self._SALE_ALIQUOT_COLUMNS

    def _l10n_ve_get_third_party_column_map(self, book_type):
        if book_type == "purchase":
            return {}
        return self._SALE_THIRD_PARTY_ALIQUOT_COLUMNS

    def _l10n_ve_get_tax_config(self, company):
        return self.env["account.tax.group"]._l10n_ve_build_tax_config(company)

    def _l10n_ve_get_ordered_aliquot_types(self, company):
        ordered_types = []
        for group in self.env["account.tax.group"]._l10n_ve_get_report_tax_groups(
            company
        ):
            report_type = group._l10n_ve_get_report_type()
            if report_type and report_type not in ordered_types:
                ordered_types.append(report_type)
        return ordered_types

    def _l10n_ve_get_tax_rate_for_type(self, company, aliquot_type, book_type):
        type_tax_use = "purchase" if book_type == "purchase" else "sale"
        return self.env["account.tax.group"]._l10n_ve_get_tax_rate_for_type(
            company, aliquot_type, type_tax_use
        )

    def _l10n_ve_get_default_tax_rates(self, company, book_type):
        return {
            aliquot_type: self._l10n_ve_get_tax_rate_for_type(
                company, aliquot_type, book_type
            )
            for aliquot_type in ("general", "reduced", "extend")
        }

    def _l10n_ve_label_to_aliquot_type(self, label, book_type, third_party=False):
        column_map = (
            self._l10n_ve_get_third_party_column_map(book_type)
            if third_party
            else self._l10n_ve_get_aliquot_column_map(book_type)
        )
        for aliquot_type, labels in column_map.items():
            if label in labels:
                return aliquot_type
        return None

    def _l10n_ve_is_aliquot_expression_label(self, label, book_type):
        column_map = self._l10n_ve_get_aliquot_column_map(book_type)
        third_party_map = self._l10n_ve_get_third_party_column_map(book_type)
        all_labels = {lbl for labels in column_map.values() for lbl in labels}
        all_labels.update(
            {lbl for labels in third_party_map.values() for lbl in labels}
        )
        return label in all_labels

    def _l10n_ve_prepare_book_columns(  # noqa: C901
        self, options, company, book_type, include_third_party=False
    ):
        columns = list(options.get("columns", []))
        column_map = self._l10n_ve_get_aliquot_column_map(book_type)
        third_party_map = (
            self._l10n_ve_get_third_party_column_map(book_type)
            if include_third_party
            else {}
        )
        main_labels = {
            lbl
            for aliquot_type, labels in column_map.items()
            if aliquot_type != "exempt"
            for lbl in labels
        }
        third_party_labels = (
            {lbl for labels in third_party_map.values() for lbl in labels}
            if third_party_map
            else set()
        )
        tax_config = self._l10n_ve_get_tax_config(company)
        configured_types = set(tax_config.keys())
        ordered_types = self._l10n_ve_get_ordered_aliquot_types(company)
        col_by_label = {col.get("expression_label"): col for col in columns}

        result = []
        index = 0
        while index < len(columns):
            column = columns[index]
            label = column.get("expression_label", "")

            if label in main_labels:
                for aliquot_type in ordered_types:
                    if aliquot_type == "exempt" or aliquot_type not in configured_types:
                        continue
                    for col_label in column_map.get(aliquot_type, []):
                        matched = col_by_label.get(col_label)
                        if matched:
                            result.append(matched)
                while (
                    index < len(columns)
                    and columns[index].get("expression_label", "") in main_labels
                ):
                    index += 1
                continue

            if include_third_party and label in third_party_labels:
                if company.l10n_ve_on_behalf_of_third_party_enabled:
                    for aliquot_type in ordered_types:
                        if (
                            aliquot_type == "exempt"
                            or aliquot_type not in configured_types
                        ):
                            continue
                        for col_label in third_party_map.get(aliquot_type, []):
                            matched = col_by_label.get(col_label)
                            if matched:
                                result.append(matched)
                while (
                    index < len(columns)
                    and columns[index].get("expression_label", "") in third_party_labels
                ):
                    index += 1
                continue

            aliquot_type = self._l10n_ve_label_to_aliquot_type(
                label, book_type, third_party=False
            )
            if aliquot_type and aliquot_type not in configured_types:
                index += 1
                continue

            third_party_type = self._l10n_ve_label_to_aliquot_type(
                label, book_type, third_party=True
            )
            if third_party_type:
                if (
                    not include_third_party
                    or not company.l10n_ve_on_behalf_of_third_party_enabled
                    or third_party_type not in configured_types
                ):
                    index += 1
                    continue

            if label.startswith("third_party_") and not (
                include_third_party and company.l10n_ve_on_behalf_of_third_party_enabled
            ):
                index += 1
                continue

            result.append(column)
            index += 1

        options["columns"] = result

    def _l10n_ve_accounting_amounts_for_tax_group(self, move, tax_group_id):
        if not move or not tax_group_id or tax_group_id == -1:
            return None
        company_currency = move.company_currency_id
        tax_lines = move.line_ids.filtered(
            lambda line: line.tax_line_id
            and line.tax_line_id.tax_group_id.id == tax_group_id
        )
        if tax_lines:
            return {
                "base_amount": company_currency.round(
                    abs(sum(tax_lines.mapped("tax_base_amount")))
                ),
                "tax_amount": company_currency.round(
                    abs(sum(tax_lines.mapped("balance")))
                ),
            }
        base_lines = move.line_ids.filtered(
            lambda line: line.display_type in ("product", "global_discount")
            and tax_group_id in line.tax_ids.tax_group_id.ids
        )
        if not base_lines:
            return None
        return {
            "base_amount": company_currency.round(
                abs(sum(base_lines.mapped("balance")))
            ),
            "tax_amount": 0.0,
        }

    def _l10n_ve_book_tax_info_from_accounting(self, move, tax_info):
        info = dict(tax_info)
        amounts = self._l10n_ve_accounting_amounts_for_tax_group(move, info.get("id"))
        if amounts:
            info["base_amount"] = amounts["base_amount"]
            info["tax_amount"] = amounts["tax_amount"]
        return info

    def _l10n_ve_apply_tax_values_from_config(
        self,
        result,
        tax_config,
        tax_info,
        tax_type,
        company,
        book_type,
        multiplier,
        move=None,
    ):
        if move:
            tax_info = self._l10n_ve_book_tax_info_from_accounting(move, tax_info)
        base = (
            tax_info.get("base_amount", tax_info.get("base_amount_currency", 0.0))
            * multiplier
        )
        amount = (
            tax_info.get("tax_amount", tax_info.get("tax_amount_currency", 0.0))
            * multiplier
        )
        if tax_type == "exempt":
            result["total_exempt"] += base
        elif tax_type == "general":
            result["base_general"] = base
            result["amount_general"] = amount
            result["percent_general"] = self._l10n_ve_get_tax_rate_for_type(
                company, "general", book_type
            )
        elif tax_type == "reduced":
            result["base_reduced"] = base
            result["amount_reduced"] = amount
            result["percent_reduced"] = self._l10n_ve_get_tax_rate_for_type(
                company, "reduced", book_type
            )
        elif tax_type == "extend":
            result["base_extend"] = base
            result["amount_extend"] = amount
            result["percent_extend"] = self._l10n_ve_get_tax_rate_for_type(
                company, "extend", book_type
            )

    def _l10n_ve_document_total_amount(self, tax_totals, multiplier):
        total = tax_totals.get("total_amount", 0.0)
        total = tax_totals.get("l10n_ve_igtf_total_without_igtf", total)
        return total * multiplier

    def _l10n_ve_book_date_bounds(self, options):
        date_values = options.get("date", {})
        date_from = date_values.get("date_from")
        date_to = date_values.get("date_to")
        return (
            fields.Date.to_date(date_from) if date_from else None,
            fields.Date.to_date(date_to) if date_to else None,
        )

    def _l10n_ve_date_outside_book_period(self, cmp_date, date_from, date_to):
        if not cmp_date:
            return False
        if date_from and cmp_date < date_from:
            return True
        if date_to and cmp_date > date_to:
            return True
        return False

    def _l10n_ve_move_outside_book_period(self, move, options):
        if not move.date:
            return True
        date_from, date_to = self._l10n_ve_book_date_bounds(options)
        return self._l10n_ve_date_outside_book_period(move.date, date_from, date_to)

    def _l10n_ve_skip_retention_line(self, retention, options, book_type):
        date_from, date_to = self._l10n_ve_book_date_bounds(options)
        if retention.date_accounting and self._l10n_ve_date_outside_book_period(
            retention.date_accounting, date_from, date_to
        ):
            return True
        if book_type == "purchase" and (
            not retention.date
            or self._l10n_ve_date_outside_book_period(
                retention.date, date_from, date_to
            )
        ):
            return True
        return False

    def _l10n_ve_book_company_ids(self, options):
        multi_company = options.get("multi_company", [])
        if multi_company:
            return [
                company["id"] for company in multi_company if company.get("selected")
            ]
        return [self.env.company.id]

    def _l10n_ve_extend_moves_with_period_retentions(
        self, moves, report, options, book_type, move_types
    ):
        if "account.retention" not in self.env:
            return moves
        date_from, date_to = self._l10n_ve_book_date_bounds(options)
        if not date_from or not date_to:
            return moves
        field_date = "date" if book_type == "purchase" else "date_accounting"
        retentions = self.env["account.retention"].search(
            [
                (field_date, ">=", date_from),
                (field_date, "<=", date_to),
                ("type", "in", move_types),
                ("type_retention", "=", "iva"),
                ("state", "=", "emitted"),
                ("company_id", "in", self._l10n_ve_book_company_ids(options)),
            ]
        )
        extra_moves = retentions.retention_line_ids.move_id.filtered(
            lambda move: move.state in ("posted", "cancel")
            and move.move_type in move_types
        )
        selected_journal_ids = [
            journal["id"] for journal in report._get_options_journals(options)
        ]
        if selected_journal_ids:
            extra_moves = extra_moves.filtered(
                lambda move: move.journal_id.id in selected_journal_ids
            )
        return (moves | extra_moves).sorted(
            key=lambda move: (move.invoice_date or move.date, move.id)
        )

    def _l10n_ve_init_tax_values_result(self, company, book_type):
        default_rates = self._l10n_ve_get_default_tax_rates(company, book_type)
        return {
            "total_taxed": 0.0,
            "total_exempt": 0.0,
            "base_general": 0.0,
            "amount_general": 0.0,
            "percent_general": default_rates.get("general", 0.0),
            "base_reduced": 0.0,
            "amount_reduced": 0.0,
            "percent_reduced": default_rates.get("reduced", 0.0),
            "base_extend": 0.0,
            "amount_extend": 0.0,
            "percent_extend": default_rates.get("extend", 0.0),
        }
