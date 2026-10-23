# Copyright 2026 andyengit
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import time

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BATCH_LINE_LIMIT = 100
BATCH_SECONDS = 30


class L10nVeBankReconcileQueue(models.Model):
    _name = "l10n.ve.bank.reconcile.queue"
    _description = "Bank Reconcile Queue"
    _order = "statement_date, id"

    statement_line_id = fields.Many2one(
        comodel_name="account.bank.statement.line",
        string="Línea de extracto",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="statement_line_id.company_id",
        store=True,
        index=True,
    )
    journal_id = fields.Many2one(
        related="statement_line_id.journal_id",
        store=True,
    )
    statement_date = fields.Date(
        related="statement_line_id.date",
        store=True,
    )
    payment_ref = fields.Char(related="statement_line_id.payment_ref")
    partner_id = fields.Many2one(related="statement_line_id.partner_id")
    currency_id = fields.Many2one(related="statement_line_id.currency_id")
    amount = fields.Monetary(related="statement_line_id.amount")

    _sql_constraints = [
        (
            "statement_line_uniq",
            "unique(statement_line_id)",
            "La línea de extracto ya está en la cola.",
        ),
    ]

    @api.model
    def _cron_process_queue(self):
        """Process one batch. Schedule the next only when lines remain."""
        entry = self.search([], limit=1)
        if not entry:
            return
        result = self._process_company_batch(entry.company_id)
        if result["remaining"] or self.search_count([]):
            self._trigger_next_batch()

    @api.model
    def _trigger_next_batch(self):
        cron = self.env.ref(
            "l10n_ve_bank_auto_reconcile.ir_cron_bank_reconcile_queue",
            raise_if_not_found=False,
        )
        if cron:
            cron._trigger()

    @api.model
    def _process_company_batch(self, company):
        """Reconcile up to BATCH_LINE_LIMIT lines or 30 seconds, then drop them from the queue."""
        entries = self.with_company(company).search(
            [("company_id", "=", company.id)],
            order="statement_date, id",
        )
        started = time.monotonic()
        processed = 0
        reconciled_count = 0
        for entry in entries:
            if (
                processed >= BATCH_LINE_LIMIT
                or time.monotonic() - started >= BATCH_SECONDS
            ):
                break
            try:
                line = entry.statement_line_id
                if line and not line.is_reconciled and line.state != "cancel":
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
            finally:
                entry.unlink()
            processed += 1
        remaining = self.search_count([("company_id", "=", company.id)])
        _logger.info(
            "Bank reference reconcile batch company %s: processed %s, "
            "reconciled %s, remaining %s",
            company.id,
            processed,
            reconciled_count,
            remaining,
        )
        return {
            "processed": processed,
            "reconciled": reconciled_count,
            "remaining": remaining,
        }
