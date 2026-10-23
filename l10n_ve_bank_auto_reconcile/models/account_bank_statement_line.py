# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import time

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BATCH_LINE_LIMIT = 25
BATCH_SECONDS = 30
JOB_CHANNEL = "root"
JOB_PRIORITY = 20
BUSY_JOB_STATES = ("wait_dependencies", "pending", "enqueued", "started")


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    def action_queue_ref_auto_reconcile(self):
        """Queue reference matching for the open bank. Does not touch the cron."""
        lines = self._pending_reference_reconcile_lines()
        if not lines:
            raise UserError(_("No hay líneas de extracto pendientes en este banco."))
        journals = lines.journal_id
        for company in lines.company_id:
            company_lines = lines.filtered(
                lambda line, company=company: line.company_id == company
            )
            self._check_reference_reconcile_not_running(company)
            self._enqueue_reference_reconcile(company, company_lines.ids)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Conciliación encolada"),
                "message": _(
                    "Se encolaron %(count)s líneas (%(journals)s). "
                    "Cada tanda procesa 25 líneas o 30 segundos, y la siguiente "
                    "empieza al terminar la anterior. No queda programado: "
                    "solo corre al pulsar este botón."
                )
                % {
                    "count": len(lines),
                    "journals": ", ".join(journals.mapped("display_name")),
                },
                "type": "success",
                "sticky": False,
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
                    if line._reconcile_by_bank_reference():
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
