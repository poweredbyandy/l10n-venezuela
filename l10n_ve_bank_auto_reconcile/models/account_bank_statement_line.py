# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import time
import unicodedata

from odoo import Command, _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BATCH_LINE_LIMIT = 25
BATCH_SECONDS = 30
JOB_CHANNEL = "root"
JOB_PRIORITY = 20
BUSY_JOB_STATES = ("wait_dependencies", "pending", "enqueued", "started")
COMMISSION_KEYWORD = "comision"
COMMISSION_MODEL_NAME = "VE: Comisión bancaria"


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def action_queue_ref_auto_reconcile(self):
        """Queue reference matching for the open bank. Does not touch the cron."""
        lines = self._pending_reference_reconcile_lines()
        if not lines:
            raise UserError(_("No hay líneas de extracto pendientes en este banco."))
        journals = lines.journal_id
        missing_account = self.env["res.company"]
        for company in lines.company_id:
            company_lines = lines.filtered(
                lambda line, company=company: line.company_id == company
            )
            if company_lines.filtered(
                lambda line: line._is_bank_commission_line()
            ) and not self.env["l10n_ve.default.account"].commission_account_for(
                company
            ):
                missing_account |= company
            self._check_reference_reconcile_not_running(company)
            self._enqueue_reference_reconcile(company, company_lines.ids)
        message = _(
            "Se encolaron %(count)s líneas (%(journals)s). "
            "Cada tanda procesa 25 líneas o 30 segundos, y la siguiente "
            "empieza al terminar la anterior. No queda programado: "
            "solo corre al pulsar este botón."
        ) % {
            "count": len(lines),
            "journals": ", ".join(journals.mapped("display_name")),
        }
        if missing_account:
            message = "%s %s" % (
                message,
                _(
                    "Las líneas con COMISION quedan pendientes hasta configurar "
                    "la cuenta de comisiones en Configuración, Cuentas por defecto."
                ),
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Conciliación encolada"),
                "message": message,
                "type": "warning" if missing_account else "success",
                "sticky": bool(missing_account),
            },
        }

    def _pending_reference_reconcile_lines(self):
        domain = [("is_reconciled", "=", False), ("state", "!=", "cancel")]
        if self:
            domain.append(("id", "in", self.ids))
        else:
            journal_id = self.env.context.get(
                "default_journal_id"
            ) or self.env.context.get("search_default_journal_id")
            if not journal_id:
                raise UserError(
                    _("Abra la conciliación de un banco para usar este botón.")
                )
            domain.append(("journal_id", "=", journal_id))
        return self.search(domain, order="date, id")

    def _check_reference_reconcile_not_running(self, company):
        busy = (
            self.env["queue.job"]
            .sudo()
            .search_count(
                [
                    ("identity_key", "=", self._reference_reconcile_identity(company)),
                    ("state", "in", list(BUSY_JOB_STATES)),
                ]
            )
        )
        if busy:
            raise UserError(
                _("Ya hay una conciliación automática en curso para este banco.")
            )

    def _reference_reconcile_identity(self, company):
        return "l10n_ve_bank_auto_reconcile:%s" % company.id

    def _enqueue_reference_reconcile(self, company, line_ids):
        description = _("Conciliar %(company)s (%(count)s líneas)") % {
            "company": company.display_name,
            "count": len(line_ids),
        }
        self.env["account.bank.statement.line"].with_delay(
            channel=JOB_CHANNEL,
            priority=JOB_PRIORITY,
            identity_key=self._reference_reconcile_identity(company),
            description=description,
        ).job_reconcile_reference_batch(line_ids, company.id)

    @api.model
    def job_reconcile_reference_batch(self, line_ids, company_id):
        """Reconcile one slice, then queue the rest. Stops at 25 lines or 30 seconds."""
        lines = self.search(
            [
                ("id", "in", list(line_ids)),
                ("is_reconciled", "=", False),
                ("state", "!=", "cancel"),
            ],
            order="date, id",
        )
        started = time.monotonic()
        processed_ids = []
        reconciled_count = 0
        for line in lines:
            if (
                len(processed_ids) >= BATCH_LINE_LIMIT
                or time.monotonic() - started >= BATCH_SECONDS
            ):
                break
            try:
                with self.env.cr.savepoint():
                    if line._is_bank_commission_line():
                        reconciled = line._reconcile_bank_commission()
                    else:
                        reconciled = (
                            line._reconcile_by_bank_reference()
                            or line._reconcile_pos_income()
                        )
                    if reconciled:
                        reconciled_count += 1
            except UserError as error:
                _logger.info(
                    "Statement line %s left for manual reconciliation: %s",
                    line.id,
                    error,
                )
            processed_ids.append(line.id)
        remaining_ids = [line.id for line in lines if line.id not in set(processed_ids)]
        if remaining_ids:
            company = self.env["res.company"].browse(company_id)
            self._enqueue_reference_reconcile(company, remaining_ids)
        _logger.info(
            "Bank reference reconcile batch company %s: processed %s, "
            "reconciled %s, remaining %s",
            company_id,
            len(processed_ids),
            reconciled_count,
            len(remaining_ids),
        )
        return {
            "processed": len(processed_ids),
            "reconciled": reconciled_count,
            "remaining": len(remaining_ids),
        }

    def _fold_bank_text(self, value):
        normalized = unicodedata.normalize("NFD", value or "")
        without_accents = "".join(
            char for char in normalized if unicodedata.category(char) != "Mn"
        )
        return without_accents.lower()

    def _is_bank_commission_line(self):
        """Venezuelan banks label fees with COMISION, with or without an accent."""
        self.ensure_one()
        return COMMISSION_KEYWORD in self._fold_bank_text(self.payment_ref)

    def _commission_writeoff_model(self):
        """Return the write-off rule for this company, kept in sync with the account."""
        self.ensure_one()
        account = self.env["l10n_ve.default.account"].commission_account_for(
            self.company_id
        )
        if not account:
            return self.env["account.reconcile.model"]
        model = self.env["account.reconcile.model"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("name", "=", COMMISSION_MODEL_NAME),
                ("rule_type", "=", "writeoff_suggestion"),
            ],
            limit=1,
        )
        line_vals = {
            "account_id": account.id,
            "amount_type": "percentage_st_line",
            "amount_string": "100",
            "label": _("Comisión bancaria"),
        }
        if not model:
            return self.env["account.reconcile.model"].create(
                {
                    "name": COMMISSION_MODEL_NAME,
                    "company_id": self.company_id.id,
                    "rule_type": "writeoff_suggestion",
                    "auto_reconcile": False,
                    "sequence": -5,
                    "match_nature": "both",
                    "match_label": "match_regex",
                    "match_label_param": r".*comisi[oó]n",
                    "line_ids": [Command.create(line_vals)],
                }
            )
        if model.line_ids[:1].account_id != account:
            if model.line_ids:
                model.line_ids[:1].account_id = account
            else:
                model.line_ids = [Command.create(line_vals)]
        return model

    def _reconcile_bank_commission(self):
        """Book a COMISION statement line to the expense account. No payment."""
        self.ensure_one()
        if self.is_reconciled or not self._is_bank_commission_line():
            return False
        rule = self._commission_writeoff_model()
        if not rule:
            _logger.info(
                "Statement line %s left pending: company %s has no bank "
                "commission account.",
                self.id,
                self.company_id.id,
            )
            return False
        wizard = (
            self.env["bank.rec.widget"]
            .with_context(default_st_line_id=self.id)
            .new({})
        )
        wizard._action_select_reconcile_model(rule)
        if wizard.state != "valid":
            return False
        wizard._action_validate()
        return bool(self.is_reconciled)

    def _pos_income_amount(self):
        self.ensure_one()
        if self.foreign_currency_id:
            return self.amount_currency, self.foreign_currency_id
        return self.amount, self.currency_id

    def _pos_income_closings(self):
        """Posted terminal closings with the same bank-credit date and amount."""
        self.ensure_one()
        amount, currency = self._pos_income_amount()
        closing_model = self.env["account.payment.closing"]
        if not currency or currency.compare_amounts(amount, 0.0) <= 0:
            return closing_model
        closings = closing_model.search(
            [
                ("company_id", "=", self.company_id.id),
                ("state", "=", "posted"),
                ("is_matched", "=", False),
                ("deposit_date", "=", self.date),
                ("currency_id", "=", currency.id),
            ]
        )
        return closings.filtered(
            lambda closing: closing.closing_line_id
            and not closing.closing_line_id.reconciled
            and currency.compare_amounts(
                closing.closing_line_id.amount_residual_currency, amount
            )
            == 0
        )

    def _unique_pos_income_closing(self):
        """One closing only. The statement journal breaks a tie; several matches wait."""
        self.ensure_one()
        closings = self._pos_income_closings()
        if not closings:
            return self.env["account.payment.closing"]
        same_journal = closings.filtered(
            lambda closing: closing.journal_id == self.journal_id
        )
        if len(same_journal) == 1:
            return same_journal
        if same_journal or len(closings) != 1:
            _logger.info(
                "Statement line %s left pending: %s terminal closings match "
                "the date and amount.",
                self.id,
                len(same_journal or closings),
            )
            return self.env["account.payment.closing"]
        return closings

    def _reconcile_pos_income(self):
        """Match a bank deposit with the open line of one posted terminal closing.

        A draft closing is ignored. The button does not create the closing.
        """
        self.ensure_one()
        if self.is_reconciled:
            return False
        closing = self._unique_pos_income_closing()
        if not closing:
            return False
        wizard = (
            self.env["bank.rec.widget"]
            .with_context(default_st_line_id=self.id)
            .new({})
        )
        wizard._action_add_new_amls(closing.closing_line_id, allow_partial=True)
        if wizard.state != "valid":
            return False
        wizard._action_validate()
        return bool(self.is_reconciled)

    def _reference_reconcile_models(self):
        self.ensure_one()
        model = self.env["account.reconcile.model"]
        if "match_ref_suffix_enabled" not in model._fields:
            rule = self.env.ref(
                "l10n_ve_bank_reconcile_ref_enterprise.account_reconcile_model_ve_ref",
                raise_if_not_found=False,
            )
            if rule and rule.active and rule.company_id == self.company_id:
                return rule
            return model.browse()
        return model.search(
            [
                ("rule_type", "=", "invoice_matching"),
                ("company_id", "=", self.company_id.id),
                ("active", "=", True),
                ("match_ref_suffix_enabled", "=", True),
            ]
        )

    def _reconcile_by_bank_reference(self):
        """Match one statement line with the reference rule and validate a unique hit.

        The reconcile model keeps auto-validate off, so the daily cron does not
        pick this up. Validation happens only inside this button job.
        """
        self.ensure_one()
        if self.is_reconciled:
            return False
        rules = self._reference_reconcile_models()
        if not rules:
            return False
        matching = rules._apply_rules(self, self._retrieve_partner())
        amls = matching.get("amls")
        if not amls or len(amls) != 1:
            return False
        wizard = (
            self.env["bank.rec.widget"]
            .with_context(default_st_line_id=self.id)
            .new({})
        )
        wizard._action_add_new_amls(
            amls, reco_model=matching.get("model"), allow_partial=True
        )
        if wizard.state != "valid":
            return False
        wizard._action_validate()
        return bool(self.is_reconciled)
