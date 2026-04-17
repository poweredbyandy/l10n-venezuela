# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import _, fields, models
from odoo.addons.web.controllers.utils import clean_action
from odoo.exceptions import UserError


class DailyPaymentsReportCustomHandler(models.AbstractModel):
    _name = "account.daily.payments.report.handler.oca"
    _inherit = "account.report.custom.handler.oca"
    _description = "Daily Payments by Journal Report Custom Handler"

    def _custom_options_initializer(self, report, options, previous_options):
        super()._custom_options_initializer(
            report, options, previous_options=previous_options
        )
        report._init_options_journals(
            options,
            previous_options=previous_options,
            additional_journals_domain=[("type", "in", ("bank", "cash"))],
        )
        report._init_options_journals_names(
            options,
            previous_options=previous_options,
            additional_journals_domain=[("type", "in", ("bank", "cash"))],
        )
        options["unfold_all"] = options.get("unfold_all", True)

        if previous_options.get("is_opening_report"):
            today = fields.Date.context_today(report)
            date_opt = options.get("date")
            if not date_opt or date_opt.get("period_type") != "today":
                options["date"] = report._get_dates_period(
                    today, today, "single", period_type="today"
                )
            options["date"]["filter"] = "this_today"
            options["date"]["period"] = 0

    def _get_custom_display_config(self):
        return {
            "css_custom_class": "daily_payments_report",
        }

    def _amount_to_report_currency(self, amount_company, company, options, conv_date):
        display_currency = self.env["res.currency"].browse(
            options["display_currency_id"]
        )
        company_currency = company.currency_id
        if not amount_company or display_currency == company_currency:
            return amount_company
        if not conv_date:
            conv_date = options["date"]["date_to"]
        return company_currency._convert(
            amount_company,
            display_currency,
            company,
            conv_date,
        )

    def _get_move_liquidity_balance(self, move, journal):
        if not journal.default_account_id:
            return 0.0
        liquidity_lines = move.line_ids.filtered(
            lambda line, acc=journal.default_account_id: line.account_id == acc
        )
        return sum(liquidity_lines.mapped("balance"))

    def _is_move_bank_liquidity_registered(self, move, journal):
        if journal.type != "bank":
            return True
        company_currency = journal.company_id.currency_id
        bal = self._get_move_liquidity_balance(move, journal)
        return not company_currency.is_zero(bal)

    def _get_move_outstanding_balance_company(self, move, journal):
        accounts = (
            journal._get_journal_inbound_outstanding_payment_accounts()
            + journal._get_journal_outbound_outstanding_payment_accounts()
        )
        if not accounts:
            return 0.0
        lines = move.line_ids.filtered(lambda line: line.account_id in accounts)
        return sum(lines.mapped("balance"))

    def _caret_options_initializer(self):
        base = self.env["account.report"]._caret_options_initializer_default()
        extra = {
            "name": _("Facturas relacionadas"),
            "action": "caret_option_daily_payments_open_invoices",
        }
        return {
            **base,
            "account.move": list(base.get("account.move", [])) + [extra],
            "account.move.line": list(base.get("account.move.line", [])) + [extra],
        }

    def caret_option_daily_payments_open_invoices(self, options, action_param):
        params = action_param or {}
        line_id = params.get("line_id")
        if not line_id:
            raise UserError(_("Línea inválida."))
        move = self._daily_payments_get_move_from_line_id(line_id)
        if not move:
            raise UserError(_("No se encontró un asiento asociado."))
        invoices = self._get_invoice_moves_for_daily_payment_line(move)
        if not invoices:
            raise UserError(_("No hay facturas vinculadas a este movimiento."))
        action = {
            "type": "ir.actions.act_window",
            "name": _("Facturas"),
            "res_model": "account.move",
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("id", "in", invoices.ids)],
            "context": {**self.env.context, "create": False},
        }
        return clean_action(action, self.env)

    def _daily_payments_get_move_from_line_id(self, line_id):
        report = self.env["account.report"]
        for _markup, model, res_id in report._parse_line_id(line_id):
            if model == "account.move" and res_id:
                return self.env["account.move"].browse(res_id)
            if model == "account.move.line" and res_id:
                return self.env["account.move.line"].browse(res_id).move_id
        return self.env["account.move"]

    def _get_invoice_moves_from_reconciliation(self, move):
        move = move[:1]
        if not move:
            return self.env["account.move"]
        invoice_types = (
            "out_invoice",
            "out_refund",
            "in_invoice",
            "in_refund",
            "out_receipt",
            "in_receipt",
        )
        seen = set()
        invoices = self.env["account.move"]
        for line in move.line_ids:
            for other in line._all_reconciled_lines():
                cm = other.move_id
                if (
                    cm.id != move.id
                    and cm.move_type in invoice_types
                    and cm.id not in seen
                ):
                    seen.add(cm.id)
                    invoices |= cm
        return invoices

    def _get_payments_linked_to_statement_line(self, st_line):
        payments = st_line.payment_ids
        if payments:
            return payments
        self.env["account.payment"].flush_model(["move_id", "outstanding_account_id"])
        self.env["account.move.line"].flush_model(
            ["move_id", "account_id", "statement_line_id"]
        )
        self.env["account.partial.reconcile"].flush_model(
            ["debit_move_id", "credit_move_id"]
        )
        self.env.cr.execute(
            """
            SELECT DISTINCT payment.id
            FROM account_payment payment
            JOIN account_move am ON am.id = payment.move_id
            JOIN account_move_line line ON line.move_id = am.id
            JOIN account_partial_reconcile part ON
                part.debit_move_id = line.id OR part.credit_move_id = line.id
            JOIN account_move_line counterpart ON
                part.debit_move_id = counterpart.id OR part.credit_move_id = counterpart.id
            WHERE payment.outstanding_account_id IS NOT NULL
              AND line.account_id = payment.outstanding_account_id
              AND line.id != counterpart.id
              AND counterpart.statement_line_id = %s
            """,
            (st_line.id,),
        )
        return self.env["account.payment"].browse(id for id, in self.env.cr.fetchall())

    def _get_invoice_moves_for_daily_payment_line(self, move):
        move = move[:1]
        if not move:
            return self.env["account.move"]
        st_line = self.env["account.bank.statement.line"].search(
            [("move_id", "=", move.id)], limit=1
        )
        if st_line:
            payments = self._get_payments_linked_to_statement_line(st_line)
            if payments:
                invoices = self.env["account.move"]
                for pay in payments:
                    invoices |= (
                        pay.invoice_ids
                        | pay.reconciled_invoice_ids
                        | pay.reconciled_bill_ids
                    )
                if invoices:
                    return invoices
        from_reco = self._get_invoice_moves_from_reconciliation(move)
        if from_reco:
            return from_reco
        if st_line:
            return self.env["account.move"]
        payment = self.env["account.payment"].search(
            [("move_id", "=", move.id)], limit=1
        )
        if payment:
            return (
                payment.invoice_ids
                | payment.reconciled_invoice_ids
                | payment.reconciled_bill_ids
            )
        return self.env["account.move"]

    def _format_invoice_documents_label(self, move):
        invoices = self._get_invoice_moves_for_daily_payment_line(move)
        if not invoices:
            return ""
        names = []
        for inv in invoices.sorted(lambda r: (r.name or "", r.id)):
            names.append(inv.name or inv.display_name or "")
        return ", ".join(n for n in names if n)

    def _bank_move_has_pending_bridge_residual(self, move, journal):
        if journal.type != "bank":
            return True
        accounts = (
            journal._get_journal_inbound_outstanding_payment_accounts()
            + journal._get_journal_outbound_outstanding_payment_accounts()
        )
        if not accounts:
            return False
        lines = move.line_ids.filtered(lambda line: line.account_id in accounts)
        company_currency = journal.company_id.currency_id
        for line in lines:
            if not company_currency.is_zero(line.amount_residual):
                return True
            if not company_currency.is_zero(line.amount_residual_currency):
                return True
        return False

    def _build_row_columns(self, report, options, values_map):
        display_currency = self.env["res.currency"].browse(
            options["display_currency_id"]
        )
        line_columns = []
        for column in options["columns"]:
            label = column["expression_label"]
            if label not in values_map:
                line_columns.append(
                    report._build_column_dict(None, column, options=options)
                )
                continue
            value = values_map[label]
            if column.get("figure_type") == "monetary":
                line_columns.append(
                    report._build_column_dict(
                        value,
                        column,
                        options=options,
                        currency=display_currency,
                    )
                )
            else:
                line_columns.append(
                    report._build_column_dict(value, column, options=options)
                )
        return line_columns

    def _get_report_date_bounds(self, options):
        date_info = options["date"]
        date_to = date_info["date_to"]
        if date_info.get("mode") == "single":
            if date_info.get("period_type") == "today":
                return date_to, date_to
            date_from = date_info.get("date_from")
            if date_from:
                return date_from, date_to
            return date_to, date_to
        date_from = date_info.get("date_from")
        if not date_from:
            return date_to, date_to
        return date_from, date_to

    def _get_selected_bank_cash_journals(self, report, options):
        selected = report._get_options_journals(options)
        journal_ids = [j["id"] for j in selected]
        journals = self.env["account.journal"].browse(journal_ids)
        journals = journals.filtered(lambda j: j.type in ("bank", "cash"))

        companies = journals.company_id
        retention_journal_ids = set(
            companies.mapped("iva_supplier_retention_journal_id").ids
            + companies.mapped("iva_customer_retention_journal_id").ids
            + companies.mapped("islr_supplier_retention_journal_id").ids
            + companies.mapped("islr_customer_retention_journal_id").ids
            + companies.mapped("municipal_supplier_retention_journal_id").ids
            + companies.mapped("municipal_customer_retention_journal_id").ids
        )
        if not retention_journal_ids:
            return journals
        return journals.filtered(lambda journal: journal.id not in retention_journal_ids)

    def _get_posted_moves_by_date(self, journal, company_ids, date_from, date_to):
        domain = [
            ("journal_id", "=", journal.id),
            ("company_id", "in", company_ids),
            ("state", "=", "posted"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ]
        return self.env["account.move"].search(domain, order="date asc, name asc")

    def _get_draft_moves(self, journal, company_ids, date_from, date_to):
        domain = [
            ("journal_id", "=", journal.id),
            ("company_id", "in", company_ids),
            ("state", "=", "draft"),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ]
        return self.env["account.move"].search(domain, order="date asc, name asc")

    def _get_outstanding_amls(
        self, journal, company_ids, date_from, date_to, exclude_move_ids
    ):
        accounts = (
            journal._get_journal_inbound_outstanding_payment_accounts()
            + journal._get_journal_outbound_outstanding_payment_accounts()
        )
        if not accounts:
            return self.env["account.move.line"]
        domain = [
            ("journal_id", "=", journal.id),
            ("company_id", "in", company_ids),
            ("account_id", "in", accounts.ids),
            ("parent_state", "=", "posted"),
            ("full_reconcile_id", "=", False),
            "|",
            ("amount_residual", "!=", 0.0),
            ("amount_residual_currency", "!=", 0.0),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ]
        amls = self.env["account.move.line"].search(domain, order="date asc, id asc")
        if not exclude_move_ids:
            return amls
        exclude = set(exclude_move_ids)
        return amls.filtered(lambda line: line.move_id.id not in exclude)

    def _dynamic_lines_generator(
        self, report, options, all_column_groups_expression_totals, warnings=None
    ):
        lines = []
        date_from, date_to = self._get_report_date_bounds(options)
        company_ids = report.get_report_company_ids(options)

        journals = self._get_selected_bank_cash_journals(report, options)
        journals = journals.sorted(lambda j: (j.company_id.name, j.name))

        totals_by_group = defaultdict(
            lambda: defaultdict(float)  # column_group_key -> amount
        )

        for journal in journals:
            journal_currency = journal.currency_id or journal.company_id.currency_id
            journal_title = _("%(journal)s — %(label)s: %(currency)s") % {
                "journal": journal.display_name,
                "label": _("Moneda del diario"),
                "currency": journal_currency.name,
            }
            lines.append(
                (
                    0,
                    {
                        "id": report._get_generic_line_id(
                            "account.journal",
                            journal.id,
                            markup="daily_pay_journal_header",
                        ),
                        "name": journal_title,
                        "columns": self._build_row_columns(report, options, {}),
                        "level": 0,
                        "unfoldable": False,
                    },
                )
            )

            posted_moves = self._get_posted_moves_by_date(
                journal, company_ids, date_from, date_to
            )
            registered_moves = posted_moves.filtered(
                lambda m, j=journal: self._is_move_bank_liquidity_registered(m, j)
            )
            pending_posted_bank_moves = (
                posted_moves - registered_moves
            ).filtered(
                lambda m, j=journal: self._bank_move_has_pending_bridge_residual(
                    m, j
                )
            )
            moves_by_date = defaultdict(list)
            for move in registered_moves:
                moves_by_date[move.date].append(move)

            if moves_by_date:
                lines.append(
                    (
                        0,
                        {
                            "id": report._get_generic_line_id(
                                "account.journal",
                                journal.id,
                                markup="daily_pay_section_done",
                            ),
                            "name": _("Pagos y cobros registrados"),
                            "columns": self._build_row_columns(report, options, {}),
                            "level": 1,
                            "unfoldable": False,
                        },
                    )
                )

            for move_date in sorted(moves_by_date.keys()):
                for move in moves_by_date[move_date]:
                    bal = self._get_move_liquidity_balance(move, journal)
                    amt = self._amount_to_report_currency(
                        bal,
                        journal.company_id,
                        options,
                        move.date,
                    )
                    for col_group_key in options["column_groups"]:
                        totals_by_group[col_group_key]["amount"] += amt
                    partner_label = move.partner_id.display_name if move.partner_id else ""
                    lines.append(
                        (
                            0,
                            {
                                "id": report._get_generic_line_id(
                                    "account.move",
                                    move.id,
                                    markup="daily_pay_posted",
                                ),
                                "name": move.name or move.display_name,
                                "columns": self._build_row_columns(
                                    report,
                                    options,
                                    {
                                        "line_date": move.date,
                                        "invoice_documents": self._format_invoice_documents_label(
                                            move
                                        ),
                                        "partner": partner_label,
                                        "amount": amt,
                                    },
                                ),
                                "level": 2,
                                "unfoldable": False,
                                "caret_options": "account.move",
                            },
                        )
                    )

            draft_moves = self._get_draft_moves(
                journal, company_ids, date_from, date_to
            )
            exclude_move_ids_for_outstanding = (
                registered_moves.ids + pending_posted_bank_moves.ids
            )
            outstanding_amls = self._get_outstanding_amls(
                journal,
                company_ids,
                date_from,
                date_to,
                exclude_move_ids_for_outstanding,
            )
            if (
                draft_moves
                or outstanding_amls
                or pending_posted_bank_moves
            ):
                lines.append(
                    (
                        0,
                        {
                            "id": report._get_generic_line_id(
                                "account.journal",
                                journal.id,
                                markup="daily_pay_section_pending",
                            ),
                            "name": _("Pendientes (borrador y cuentas puente)"),
                            "columns": self._build_row_columns(report, options, {}),
                            "level": 1,
                            "unfoldable": False,
                        },
                    )
                )

                for move in draft_moves:
                    bal = self._get_move_liquidity_balance(move, journal)
                    amt = self._amount_to_report_currency(
                        bal,
                        journal.company_id,
                        options,
                        move.date,
                    )
                    for col_group_key in options["column_groups"]:
                        totals_by_group[col_group_key]["amount"] += amt
                    partner_label = (
                        move.partner_id.display_name if move.partner_id else ""
                    )
                    lines.append(
                        (
                            0,
                            {
                                "id": report._get_generic_line_id(
                                    "account.move",
                                    move.id,
                                    markup="daily_pay_draft",
                                ),
                                "name": move.name or _("Borrador"),
                                "columns": self._build_row_columns(
                                    report,
                                    options,
                                    {
                                        "line_date": move.date,
                                        "invoice_documents": self._format_invoice_documents_label(
                                            move
                                        ),
                                        "partner": partner_label,
                                        "amount": amt,
                                    },
                                ),
                                "level": 2,
                                "unfoldable": False,
                                "caret_options": "account.move",
                            },
                        )
                    )

                for move in pending_posted_bank_moves.sorted(
                    lambda m: (m.date, m.name or "")
                ):
                    bal = self._get_move_outstanding_balance_company(move, journal)
                    amt = self._amount_to_report_currency(
                        bal,
                        journal.company_id,
                        options,
                        move.date,
                    )
                    for col_group_key in options["column_groups"]:
                        totals_by_group[col_group_key]["amount"] += amt
                    partner_label = move.partner_id.display_name if move.partner_id else ""
                    lines.append(
                        (
                            0,
                            {
                                "id": report._get_generic_line_id(
                                    "account.move",
                                    move.id,
                                    markup="daily_pay_bank_pending",
                                ),
                                "name": move.name or move.display_name,
                                "columns": self._build_row_columns(
                                    report,
                                    options,
                                    {
                                        "line_date": move.date,
                                        "invoice_documents": self._format_invoice_documents_label(
                                            move
                                        ),
                                        "partner": partner_label,
                                        "amount": amt,
                                    },
                                ),
                                "level": 2,
                                "unfoldable": False,
                                "caret_options": "account.move",
                            },
                        )
                    )

                for aml in outstanding_amls:
                    amt = self._amount_to_report_currency(
                        aml.amount_residual,
                        journal.company_id,
                        options,
                        aml.date,
                    )
                    for col_group_key in options["column_groups"]:
                        totals_by_group[col_group_key]["amount"] += amt
                    move = aml.move_id
                    partner_label = aml.partner_id.display_name if aml.partner_id else ""
                    short_name = (move.name if move else None) or aml.move_name or _(
                        "Línea pendiente"
                    )
                    lines.append(
                        (
                            0,
                            {
                                "id": report._get_generic_line_id(
                                    "account.move.line",
                                    aml.id,
                                    markup="daily_pay_outstanding",
                                ),
                                "name": short_name,
                                "columns": self._build_row_columns(
                                    report,
                                    options,
                                    {
                                        "line_date": aml.date,
                                        "invoice_documents": self._format_invoice_documents_label(
                                            aml.move_id
                                        ),
                                        "partner": partner_label,
                                        "amount": amt,
                                    },
                                ),
                                "level": 2,
                                "unfoldable": False,
                                "caret_options": "account.move.line",
                            },
                        )
                    )

        total_line_columns = []
        for column in options["columns"]:
            label = column["expression_label"]
            col_group_key = column["column_group_key"]
            if label == "amount":
                display_currency = self.env["res.currency"].browse(
                    options["display_currency_id"]
                )
                total_line_columns.append(
                    report._build_column_dict(
                        totals_by_group[col_group_key]["amount"],
                        column,
                        options=options,
                        currency=display_currency,
                    )
                )
            else:
                total_line_columns.append(
                    report._build_column_dict(None, column, options=options)
                )

        lines.append(
            (
                0,
                {
                    "id": report._get_generic_line_id(
                        None, None, markup="daily_pay_total"
                    ),
                    "name": _("Total"),
                    "columns": total_line_columns,
                    "level": 0,
                    "unfoldable": False,
                    "class": "total",
                },
            )
        )

        return lines
