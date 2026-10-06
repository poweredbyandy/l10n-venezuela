# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, fields, models
from odoo.exceptions import UserError

LOAD_MORE_LIMIT = 80


class L10nVeLiquidityBookReportMixin(models.AbstractModel):
    _name = "l10n.ve.liquidity.book.report.mixin"
    _inherit = "account.report.custom.handler.oca"
    _description = "Mixin for Venezuelan bank and cash auxiliary books"

    def _get_journal_types(self):
        raise NotImplementedError

    def _get_custom_display_config(self):
        return {
            "css_custom_class": "liquidity_book_report",
        }

    def _custom_options_initializer(self, report, options, previous_options):
        result = super()._custom_options_initializer(
            report, options, previous_options=previous_options
        )
        report._init_options_journals(
            options,
            previous_options=previous_options,
            additional_journals_domain=[("type", "in", self._get_journal_types())],
        )
        if "unfold_all" not in previous_options:
            options["unfold_all"] = True
        return result

    def export_to_pdf(self, options):
        report = self.env["account.report"].browse(options["report_id"])
        return type(report).export_to_pdf(
            report.with_context(force_landscape_printing=True), options
        )

    def _get_liquidity_account(self, journal):
        return journal.default_account_id

    def _get_selected_journals(self, report, options):
        selected = report._get_options_journals(options)
        journal_ids = [journal["id"] for journal in selected]
        journals = self.env["account.journal"].browse(journal_ids)
        return journals.filtered(
            lambda journal: journal.type in self._get_journal_types()
        ).sorted(lambda journal: (journal.company_id.name, journal.name))

    def _to_report_date(self, value):
        if not value:
            return False
        if isinstance(value, str):
            return fields.Date.from_string(value)
        return value

    def _get_report_date_bounds(self, options):
        date_info = options["date"]
        date_from = self._to_report_date(date_info.get("date_from"))
        date_to = self._to_report_date(date_info["date_to"])
        if not date_from:
            date_from = date_to
        return date_from, date_to

    def _get_move_line_domain(self, report, options, account_ids, date_from, date_to):
        domain = [
            ("account_id", "in", list(account_ids)),
            ("company_id", "in", report.get_report_company_ids(options)),
            ("parent_state", "=", "posted"),
        ]
        if date_from:
            domain.append(("date", ">=", date_from))
        if date_to:
            domain.append(("date", "<=", date_to))
        return domain

    def _get_opening_balances(self, report, options, account_ids):
        if not account_ids:
            return {}
        date_from, _date_to = self._get_report_date_bounds(options)
        groups = self.env["account.move.line"]._read_group(
            [
                ("account_id", "in", list(account_ids)),
                ("company_id", "in", report.get_report_company_ids(options)),
                ("parent_state", "=", "posted"),
                ("date", "<", date_from),
            ],
            ["account_id"],
            ["balance:sum"],
        )
        return {account.id: float(balance or 0.0) for account, balance in groups}

    def _get_period_aggregates(self, report, options, account_ids):
        if not account_ids:
            return {}
        date_from, date_to = self._get_report_date_bounds(options)
        groups = self.env["account.move.line"]._read_group(
            self._get_move_line_domain(
                report, options, account_ids, date_from, date_to
            ),
            ["account_id"],
            ["debit:sum", "credit:sum", "__count"],
        )
        return {
            account.id: {
                "debit": float(debit or 0.0),
                "credit": float(credit or 0.0),
                "count": count or 0,
            }
            for account, debit, credit, count in groups
        }

    def _get_screen_limit(self, report, options):
        if options.get("export_mode") in ("print", "file"):
            return None
        return report.load_more_limit or LOAD_MORE_LIMIT

    def _get_account_move_lines(
        self, report, options, account_id, offset=0, limit=None
    ):
        date_from, date_to = self._get_report_date_bounds(options)
        return self.env["account.move.line"].search(
            self._get_move_line_domain(
                report, options, [account_id], date_from, date_to
            ),
            order="date asc, move_id asc, id asc",
            offset=offset,
            limit=limit,
        )

    def _balance_progress(self, options, running_balance):
        return {
            column_group_key: running_balance
            for column_group_key in options["column_groups"]
        }

    def _progress_balance(self, options, progress):
        if not progress or not options.get("column_groups"):
            return 0.0
        column_group_key = next(iter(options["column_groups"]))
        return float(progress.get(column_group_key) or 0.0)

    def _build_row_columns(self, report, options, values_map):
        line_columns = []
        for column in options["columns"]:
            label = column["expression_label"]
            if label not in values_map:
                line_columns.append(
                    report._build_column_dict(None, column, options=options)
                )
                continue
            line_columns.append(
                report._build_column_dict(values_map[label], column, options=options)
            )
        return line_columns

    def _build_amount_total_columns(
        self, report, options, amounts_by_column_group, amount_labels
    ):
        columns = []
        for column in options["columns"]:
            label = column["expression_label"]
            col_group_key = column["column_group_key"]
            if label in amount_labels:
                columns.append(
                    report._build_column_dict(
                        amounts_by_column_group[col_group_key].get(label, 0.0),
                        column,
                        options=options,
                    )
                )
            else:
                columns.append(report._build_column_dict(None, column, options=options))
        return columns

    def _get_move_detail_label(self, aml):
        journal_code = aml.journal_id.code or ""
        journal_info = f"[{journal_code}]" if journal_code else ""
        line_name = aml.name or ""
        return f"{journal_info} {line_name}".strip()

    def _get_move_comp_number(self, aml):
        return aml.ref or aml.move_id.name or ""

    def _empty_amount_bucket(self):
        return {
            "previous_balance": 0.0,
            "debit": 0.0,
            "credit": 0.0,
            "balance": 0.0,
        }

    def _journal_amount_bucket(self, previous_balance, period):
        debit = period.get("debit", 0.0)
        credit = period.get("credit", 0.0)
        return {
            "previous_balance": previous_balance,
            "debit": debit,
            "credit": credit,
            "balance": previous_balance + debit - credit,
        }

    def _is_journal_unfolded(self, options, line_id, has_moves):
        if not has_moves:
            return False
        if options.get("export_mode") in ("print", "file"):
            return True
        if options.get("unfold_all"):
            return True
        return line_id in options.get("unfolded_lines", [])

    def _dynamic_lines_generator(
        self, report, options, all_column_groups_expression_totals, warnings=None
    ):
        lines = []
        journals = self._get_selected_journals(report, options)
        column_group_keys = list(options["column_groups"])
        totals_by_group = {
            column_group_key: self._empty_amount_bucket()
            for column_group_key in column_group_keys
        }
        account_ids = [
            account.id
            for journal in journals
            if (account := self._get_liquidity_account(journal))
        ]
        opening_balances = self._get_opening_balances(report, options, account_ids)
        period_aggregates = self._get_period_aggregates(report, options, account_ids)

        for journal in journals:
            account = self._get_liquidity_account(journal)
            if not account:
                continue

            previous_balance = opening_balances.get(account.id, 0.0)
            period = period_aggregates.get(account.id, {})
            journal_amounts = self._journal_amount_bucket(previous_balance, period)
            journal_totals = {
                column_group_key: dict(journal_amounts)
                for column_group_key in column_group_keys
            }
            for column_group_key in column_group_keys:
                for label in ("previous_balance", "debit", "credit", "balance"):
                    totals_by_group[column_group_key][label] += journal_amounts[label]

            line_id = report._get_generic_line_id(
                "account.journal",
                journal.id,
                markup="liquidity_book_journal_header",
            )
            has_moves = bool(period.get("count"))
            lines.append(
                (
                    0,
                    {
                        "id": line_id,
                        "name": _("%(journal)s — %(account)s")
                        % {
                            "journal": journal.display_name,
                            "account": account.display_name,
                        },
                        "columns": self._build_row_columns(report, options, {}),
                        "level": 0,
                        "unfoldable": has_moves,
                        "unfolded": self._is_journal_unfolded(
                            options, line_id, has_moves
                        ),
                        "expand_function": (
                            "_report_expand_unfoldable_line_liquidity_book"
                            if has_moves
                            else None
                        ),
                    },
                )
            )
            lines.append(
                (
                    0,
                    {
                        "id": report._get_generic_line_id(
                            "account.journal",
                            journal.id,
                            markup="liquidity_book_journal_total",
                        ),
                        "name": _("Total (%(journal)s)", journal=journal.display_name),
                        "columns": self._build_amount_total_columns(
                            report,
                            options,
                            journal_totals,
                            (
                                "previous_balance",
                                "debit",
                                "credit",
                                "balance",
                            ),
                        ),
                        "level": 1,
                        "unfoldable": False,
                        "class": "total",
                    },
                )
            )

        if journals:
            lines.append(
                (
                    0,
                    {
                        "id": report._get_generic_line_id(
                            None, None, markup="liquidity_book_total"
                        ),
                        "name": _("Total"),
                        "columns": self._build_amount_total_columns(
                            report,
                            options,
                            totals_by_group,
                            (
                                "previous_balance",
                                "debit",
                                "credit",
                                "balance",
                            ),
                        ),
                        "level": 0,
                        "unfoldable": False,
                        "class": "total",
                    },
                )
            )

        return lines

    def _report_expand_unfoldable_line_liquidity_book(
        self,
        line_dict_id,
        groupby,
        options,
        progress,
        offset,
        unfold_all_batch_data=None,
    ):
        report = self.env["account.report"].browse(options["report_id"])
        model, journal_id = report._get_model_info_from_id(line_dict_id)
        if model != "account.journal":
            raise UserError(
                _("Wrong ID for liquidity book line to expand: %s", line_dict_id)
            )

        journal = self.env["account.journal"].browse(journal_id)
        account = self._get_liquidity_account(journal)
        if not account:
            return {
                "lines": [],
                "offset_increment": 0,
                "has_more": False,
                "progress": progress,
            }

        if offset:
            running_balance = self._progress_balance(options, progress)
        else:
            running_balance = self._get_opening_balances(
                report, options, [account.id]
            ).get(account.id, 0.0)

        limit = self._get_screen_limit(report, options)
        move_lines = self._get_account_move_lines(
            report,
            options,
            account.id,
            offset=offset,
            limit=(limit + 1) if limit else None,
        )
        has_more = bool(limit and len(move_lines) > limit)
        if has_more:
            move_lines = move_lines[:limit]

        lines = []
        for aml in move_lines:
            debit = aml.debit
            credit = aml.credit
            running_balance += debit - credit
            lines.append(
                {
                    "id": report._get_generic_line_id(
                        "account.move.line",
                        aml.id,
                        parent_line_id=line_dict_id,
                        markup="liquidity_book_line",
                    ),
                    "parent_id": line_dict_id,
                    "name": account.code,
                    "columns": self._build_row_columns(
                        report,
                        options,
                        {
                            "date": aml.date,
                            "comp_number": self._get_move_comp_number(aml),
                            "document": aml.move_id.name or "",
                            "detail": self._get_move_detail_label(aml),
                            "debit": debit,
                            "credit": credit,
                            "balance": running_balance,
                        },
                    ),
                    "level": 1,
                    "unfoldable": False,
                    "caret_options": "account.move.line",
                }
            )

        return {
            "lines": lines,
            "offset_increment": limit or len(lines),
            "has_more": has_more,
            "progress": self._balance_progress(options, running_balance),
        }
