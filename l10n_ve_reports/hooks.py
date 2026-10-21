# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)

_MOVE_TYPES = ("out_invoice", "out_refund", "in_invoice", "in_refund")


def _tax_totals_company_base_by_group(move):
    bases = {}
    for subtotal in (move.tax_totals or {}).get("subtotals") or []:
        for tax_group in subtotal.get("tax_groups") or []:
            group_id = tax_group.get("id")
            if not group_id or group_id == -1:
                continue
            bases[group_id] = abs(tax_group.get("base_amount") or 0.0)
    return bases


def align_posted_tax_base_to_tax_totals(env, moves=None):
    if moves is None:
        env.cr.execute(
            """
            SELECT move.id
              FROM account_move AS move
             WHERE move.state = 'posted'
               AND move.move_type IN %s
            """,
            (_MOVE_TYPES,),
        )
        moves = env["account.move"].browse([row[0] for row in env.cr.fetchall()])
    else:
        moves = moves.filtered(
            lambda move: move.state == "posted" and move.move_type in _MOVE_TYPES
        )
    updated = skipped = 0
    for move in moves:
        company_currency = move.company_currency_id
        targets = _tax_totals_company_base_by_group(move)
        if not targets:
            skipped += 1
            continue
        changed = False
        for group_id, target_base in targets.items():
            lines = move.line_ids.filtered(
                lambda line, group_id=group_id: line.tax_line_id
                and line.tax_line_id.tax_group_id.id == group_id
            )
            if not lines:
                continue
            current = abs(sum(lines.mapped("tax_base_amount")))
            if not company_currency.compare_amounts(current, target_base):
                continue
            delta = company_currency.round(target_base - current)
            line = lines[0]
            env.cr.execute(
                """
                UPDATE account_move_line
                   SET tax_base_amount = %s
                 WHERE id = %s
                """,
                (line.tax_base_amount + delta, line.id),
            )
            line.invalidate_recordset(["tax_base_amount"])
            changed = True
        if changed:
            updated += 1
        else:
            skipped += 1
    _logger.info(
        "l10n_ve_reports: aligned tax_base_amount on %s moves, skipped %s",
        updated,
        skipped,
    )
    return updated, skipped
