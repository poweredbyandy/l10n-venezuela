# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Implementation loaded by fiscal_audit_align.run_fiscal_audit_align().
# Do not call this file directly; use the public API from the shell.

from collections import defaultdict

from odoo.tools import float_compare, float_is_zero, float_round

APPLY = globals().get("APPLY", False)
MOVE_NAMES = globals().get("MOVE_NAMES", [])
DATE_FROM = globals().get("DATE_FROM", False)
DATE_TO = globals().get("DATE_TO", False)
DIFF_THRESHOLD = globals().get("DIFF_THRESHOLD", 0.01)

FLAG_21 = {
    "30": {"amount_int": 14, "amount_dec": 2, "qty_int": 14, "qty_dec": 3},
    "00": {"amount_int": 8, "amount_dec": 2, "qty_int": 5, "qty_dec": 3},
    "01": {"amount_int": 7, "amount_dec": 3, "qty_int": 5, "qty_dec": 3},
    "02": {"amount_int": 6, "amount_dec": 4, "qty_int": 5, "qty_dec": 3},
}
TAX_RATE_BY_PREFIX = {
    " ": 0.0,
    "!": 16.0,
    '"': 8.0,
    "#": 31.0,
}
PRODUCT_CMD_PREFIXES = set(TAX_RATE_BY_PREFIX)


def _product_price_prec():
    return env["decimal.precision"].precision_get("Product Price")


def _flag21_for_move(move):
    company = move.company_id
    for field_name in (
        "l10n_ve_fiscal_flag_21",
        "l10n_ve_flag_21",
        "fiscal_flag_21",
    ):
        if field_name in company._fields and company[field_name]:
            return str(company[field_name])
    return "00"


def _parse_product_command(payload, flag21):
    if not payload or payload[0] not in PRODUCT_CMD_PREFIXES:
        return None
    cfg = FLAG_21.get(flag21) or FLAG_21["00"]
    body = payload[1:]
    amount_len = cfg["amount_int"] + cfg["amount_dec"]
    qty_len = cfg["qty_int"] + cfg["qty_dec"]
    if len(body) < amount_len + qty_len:
        return None
    amount_raw = body[:amount_len]
    qty_raw = body[amount_len : amount_len + qty_len]
    rest = body[amount_len + qty_len :]
    if not amount_raw.isdigit() or not qty_raw.isdigit():
        return None
    unit = int(amount_raw[: cfg["amount_int"]]) + int(
        amount_raw[cfg["amount_int"] :]
    ) / (10 ** cfg["amount_dec"])
    qty = int(qty_raw[: cfg["qty_int"]]) + int(qty_raw[cfg["qty_int"] :]) / (
        10 ** cfg["qty_dec"]
    )
    code = False
    if rest.startswith("|"):
        parts = rest.split("|", 2)
        if len(parts) >= 3:
            code = parts[1] or False
    prec = _product_price_prec()
    unit = float_round(unit, precision_digits=prec)
    rate = TAX_RATE_BY_PREFIX.get(payload[0], 0.0)
    base = float_round(unit * qty, precision_digits=2)
    tax = float_round(base * rate / 100.0, precision_digits=2) if rate else 0.0
    return {
        "prefix": payload[0],
        "unit": unit,
        "qty": qty,
        "code": code,
        "base": base,
        "tax": tax,
        "rate": rate,
        "payload": payload,
    }


def _audit_product_lines(move):
    Audit = env["l10n.ve.fiscal.serial.audit"]
    cmds = Audit.search(
        [
            ("move_id", "=", move.id),
            ("event_type", "=", "command"),
            ("command_step", "=", "SEND_CMD_REQUEST"),
            ("success", "=", True),
        ],
        order="id",
    )
    flag21 = _flag21_for_move(move)
    lines = []
    for audit in cmds:
        parsed = _parse_product_command(audit.command_payload or "", flag21)
        if parsed:
            lines.append(parsed)
    return lines


def _printed_amounts(move, audit_lines):
    company_currency = move.company_currency_id
    base = company_currency.round(sum(line["base"] for line in audit_lines))
    tax = company_currency.round(sum(line["tax"] for line in audit_lines))
    return base, tax, company_currency.round(base + tax)


def _aml_write(line, vals):
    line.with_context(
        check_move_validity=False,
        skip_invoice_line_sync=True,
        tracking_disable=True,
    ).write(vals)


def _scale_balances(lines, target_abs):
    lines = list(lines)
    if not lines:
        return
    company_currency = lines[0].company_currency_id
    current = sum(abs(line.balance) for line in lines)
    assigned = 0.0
    for index, line in enumerate(lines):
        if index == len(lines) - 1:
            new_abs = company_currency.round(target_abs - assigned)
        elif current:
            new_abs = company_currency.round(abs(line.balance) * target_abs / current)
            assigned += new_abs
        else:
            new_abs = 0.0
        if line.balance < 0:
            _aml_write(
                line,
                {
                    "balance": -new_abs,
                    "credit": new_abs,
                    "debit": 0.0,
                },
            )
        else:
            _aml_write(
                line,
                {
                    "balance": new_abs,
                    "debit": new_abs,
                    "credit": 0.0,
                },
            )


def _scale_tax_base(lines, target_abs):
    lines = list(lines)
    if not lines:
        return
    company_currency = lines[0].company_currency_id
    current = sum(abs(line.tax_base_amount) for line in lines)
    assigned = 0.0
    for index, line in enumerate(lines):
        if index == len(lines) - 1:
            new_abs = company_currency.round(target_abs - assigned)
        elif current:
            new_abs = company_currency.round(
                abs(line.tax_base_amount) * target_abs / current
            )
            assigned += new_abs
        else:
            new_abs = 0.0
        _aml_write(line, {"tax_base_amount": new_abs})


def _fix_move_imbalance(move):
    """Absorbe céntimos de redondeo en la línea de producto (o impuesto)."""
    env.flush_all()
    move.invalidate_recordset()
    move.line_ids.invalidate_recordset()
    company_currency = move.company_currency_id
    imbalance = company_currency.round(sum(move.line_ids.mapped("balance")))
    if float_is_zero(imbalance, precision_rounding=company_currency.rounding):
        return
    sink = move.line_ids.filtered(lambda line: line.display_type == "product")[:1]
    if not sink:
        sink = move.line_ids.filtered("tax_line_id")[:1]
    if not sink:
        sink = move.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )[:1]
    if not sink:
        raise ValueError("Asiento desbalanceado sin línea para ajustar en %s" % move.name)
    new_balance = company_currency.round(sink.balance - imbalance)
    if new_balance < 0:
        _aml_write(
            sink,
            {
                "balance": new_balance,
                "credit": abs(new_balance),
                "debit": 0.0,
            },
        )
    else:
        _aml_write(
            sink,
            {
                "balance": new_balance,
                "debit": abs(new_balance),
                "credit": 0.0,
            },
        )
    env.flush_all()
    move.invalidate_recordset()
    left = company_currency.round(sum(move.line_ids.mapped("balance")))
    if not float_is_zero(left, precision_rounding=company_currency.rounding):
        raise ValueError(
            "No se pudo balancear %s (resto %s)" % (move.name, left)
        )


def _sync_product_company_amounts(move):
    """
    Alinea price_subtotal_currency (y campos relacionados) al crédito/débito
    del apunte, para que el subtotal en Bs coincida con el asiento / máquina.
    """
    product_lines = move.line_ids.filtered(lambda line: line.display_type == "product")
    for line in product_lines:
        target = abs(line.balance)
        vals = {}
        if "price_subtotal_currency" in line._fields and float_compare(
            abs(line.price_subtotal_currency or 0.0),
            target,
            precision_rounding=move.company_currency_id.rounding,
        ):
            vals["price_subtotal_currency"] = target
        if (
            "l10n_ve_price_subtotal_wo_discount_currency" in line._fields
            and not line.discount
            and float_compare(
                abs(line.l10n_ve_price_subtotal_wo_discount_currency or 0.0),
                target,
                precision_rounding=move.company_currency_id.rounding,
            )
        ):
            vals["l10n_ve_price_subtotal_wo_discount_currency"] = target
        if vals:
            _aml_write(line, vals)


def _is_exchange_move(move):
    company = move.company_id
    if company.currency_exchange_journal_id and move.journal_id == company.currency_exchange_journal_id:
        return True
    if move.journal_id.code == "EXCH":
        return True
    name = move.name or ""
    return name.startswith("EXCH/")


def _payment_term_counterparts(move):
    term_lines = move.line_ids.filtered(lambda line: line.display_type == "payment_term")
    counterparts = env["account.move.line"]
    for line in term_lines:
        counterparts |= line.matched_debit_ids.mapped("debit_move_id")
        counterparts |= line.matched_credit_ids.mapped("credit_move_id")
    # Quedarnos con cobros reales (no asientos EXCH que Odoo borra al desconciliar).
    counterparts = counterparts.filtered(lambda line: not _is_exchange_move(line.move_id))
    return term_lines, counterparts


def _is_paid_like(move):
    """Paid for this fix: payment_state paid, or in_payment with residual 0."""
    if move.payment_state == "reversed":
        return False
    residual_zero = float_is_zero(
        move.amount_residual_signed,
        precision_rounding=move.company_currency_id.rounding,
    )
    if move.payment_state == "paid":
        return True
    if move.payment_state == "in_payment" and residual_zero:
        return True
    return False


def _align_payment_account(term_lines, counterparts):
    """Si el cobro está en otra CxC (p.ej. .001 vs Cashea .005), alinear cuenta."""
    if not term_lines or not counterparts:
        return counterparts
    accounts = term_lines.mapped("account_id")
    if len(accounts) != 1:
        return counterparts
    term_account = accounts
    for line in counterparts:
        if (
            line.account_id != term_account
            and line.account_id.account_type == "asset_receivable"
            and not line.reconciled
        ):
            line.with_context(
                check_move_validity=False,
                skip_invoice_line_sync=True,
                tracking_disable=True,
            ).write({"account_id": term_account.id})
    return counterparts.exists()


def _exchange_journal(company):
    journal = company.currency_exchange_journal_id
    if journal:
        return journal
    journal = env["account.journal"].search(
        [("company_id", "=", company.id), ("code", "=", "EXCH")],
        limit=1,
    )
    if journal:
        return journal
    return env["account.journal"].search(
        [("company_id", "=", company.id), ("type", "=", "general")],
        limit=1,
    )


def _reconcile_by_account(*line_groups):
    """Reconcile only amls that share the same account (Cashea vs CxC, etc.)."""
    amls = env["account.move.line"]
    for group in line_groups:
        amls |= group
    amls = amls.filtered(lambda line: not line.reconciled)
    for account in amls.mapped("account_id"):
        group = amls.filtered(lambda line: line.account_id == account)
        if len(group) < 2:
            continue
        group.with_context(no_exchange_difference=True).reconcile()


def _open_term_lines(move):
    company_currency = move.company_currency_id
    lines = move.line_ids.filtered(
        lambda line: line.display_type == "payment_term" and not line.reconciled
    )
    open_lines = env["account.move.line"]
    for line in lines:
        company_open = not float_is_zero(
            line.amount_residual, precision_rounding=company_currency.rounding
        )
        currency_open = line.currency_id and not float_is_zero(
            line.amount_residual_currency,
            precision_rounding=line.currency_id.rounding,
        )
        if company_open or currency_open:
            open_lines |= line
    return open_lines


def _create_and_reconcile_difference(move, term_open):
    """
    Asiento EXCH por residual abierto (mismo criterio que Odoo exchange):
    residual > 0 → pérdida (crédito CxC) ; residual < 0 → ganancia (débito CxC).
    Cada línea del diferencial en CxC se concilia con su vencimiento.
    """
    company = move.company_id
    company_currency = company.currency_id
    journal = _exchange_journal(company)
    if not journal:
        raise ValueError(
            "Sin diario de diferencia en cambio / EXCH en %s" % company.display_name
        )
    if not company.income_currency_exchange_account_id:
        raise ValueError(
            "Falta cuenta de ganancia por diferencia en cambio en %s"
            % company.display_name
        )
    if not company.expense_currency_exchange_account_id:
        raise ValueError(
            "Falta cuenta de pérdida por diferencia en cambio en %s"
            % company.display_name
        )

    diff_moves = env["account.move"]
    kinds = []
    for term in term_open:
        amount_residual = term.amount_residual
        amount_residual_currency = term.amount_residual_currency
        if float_is_zero(amount_residual, precision_rounding=company_currency.rounding):
            if not (
                term.currency_id
                and not float_is_zero(
                    amount_residual_currency,
                    precision_rounding=term.currency_id.rounding,
                )
            ):
                continue
            amount_residual_to_fix = amount_residual_currency
        else:
            amount_residual_to_fix = amount_residual

        gain = amount_residual_to_fix < 0
        exch_account = (
            company.income_currency_exchange_account_id
            if gain
            else company.expense_currency_exchange_account_id
        )
        label = (
            "Ganancia por diferencia fiscal %s" % move.name
            if gain
            else "Pérdida por diferencia fiscal %s" % move.name
        )
        # Igual que account.move.line._prepare_exchange_difference_move_vals
        ar_vals = {
            "name": label,
            "account_id": term.account_id.id,
            "partner_id": term.partner_id.id,
            "currency_id": term.currency_id.id,
            "debit": -amount_residual if amount_residual < 0.0 else 0.0,
            "credit": amount_residual if amount_residual > 0.0 else 0.0,
            "amount_currency": -amount_residual_currency,
        }
        pl_vals = {
            "name": label,
            "account_id": exch_account.id,
            "partner_id": term.partner_id.id,
            "currency_id": term.currency_id.id,
            "debit": amount_residual if amount_residual > 0.0 else 0.0,
            "credit": -amount_residual if amount_residual < 0.0 else 0.0,
            "amount_currency": amount_residual_currency,
        }
        diff_move = env["account.move"].create(
            {
                "move_type": "entry",
                "journal_id": journal.id,
                "date": move.date,
                "ref": label,
                "company_id": company.id,
                "line_ids": [(0, 0, ar_vals), (0, 0, pl_vals)],
            }
        )
        diff_move.action_post()
        exch_ar = diff_move.line_ids.filtered(
            lambda line: line.account_id == term.account_id and not line.reconciled
        )
        if term and exch_ar:
            (term + exch_ar).with_context(no_exchange_difference=True).reconcile()
        diff_moves |= diff_move
        kinds.append("gain" if gain else "loss")

    kind = False
    if kinds:
        if all(k == "gain" for k in kinds):
            kind = "gain"
        elif all(k == "loss" for k in kinds):
            kind = "loss"
        else:
            kind = "mixed"
    return diff_moves, kind


def _align_move(move, audit_lines, dry_run=True):
    company_currency = move.company_currency_id
    printed_base, printed_tax, printed_total = _printed_amounts(move, audit_lines)
    current_total = abs(move.amount_total_signed)
    current_tax = abs(move.amount_tax_signed)
    current_base = abs(move.amount_untaxed_signed)
    delta_total = company_currency.round(printed_total - current_total)
    paid_like = _is_paid_like(move)
    report = {
        "name": move.name,
        "fiscal": move.l10n_ve_invoice_number,
        "payment_state": move.payment_state,
        "residual": abs(move.amount_residual_signed),
        "paid_like": paid_like,
        "audit_lines": len(audit_lines),
        "current_base": current_base,
        "current_tax": current_tax,
        "current_total": current_total,
        "printed_base": printed_base,
        "printed_tax": printed_tax,
        "printed_total": printed_total,
        "delta_total": delta_total,
        "units": [
            (line["code"] or "", line["unit"], line["qty"], line["base"], line["tax"])
            for line in audit_lines
        ],
        "action": "skip",
        "diff_entry": False,
        "diff_move": False,
    }
    if move.payment_state == "reversed":
        report["action"] = "skip_reversed"
        return report

    totals_ok = (
        abs(delta_total) < DIFF_THRESHOLD
        and abs(printed_tax - current_tax) < DIFF_THRESHOLD
    )

    if dry_run:
        if totals_ok:
            report["action"] = "already_ok"
            return report
        report["action"] = "would_align"
        if paid_like and abs(delta_total) >= DIFF_THRESHOLD:
            report["diff_entry"] = "gain" if delta_total < 0 else "loss"
        elif not paid_like:
            report["diff_entry"] = "keep_residual"
        return report

    term_lines, counterparts = _payment_term_counterparts(move)
    counterpart_ids = counterparts.ids

    if totals_ok:
        # Totales ya alineados: sincronizar subtotal Bs al apunte y, si aplica,
        # cerrar residual suelto en cobro/vencimiento.
        _sync_product_company_amounts(move)
        if paid_like:
            counterparts.invalidate_recordset()
            to_clear = _open_term_lines(move)
            to_clear |= counterparts.filtered(
                lambda line: not line.reconciled
                and (
                    not float_is_zero(
                        line.amount_residual,
                        precision_rounding=company_currency.rounding,
                    )
                    or (
                        line.currency_id
                        and not float_is_zero(
                            line.amount_residual_currency,
                            precision_rounding=line.currency_id.rounding,
                        )
                    )
                )
            )
            if to_clear:
                diff_moves, kind = _create_and_reconcile_difference(move, to_clear)
                report["action"] = "aligned"
                report["diff_entry"] = kind or False
                report["diff_move"] = (
                    ", ".join(diff_moves.mapped("name")) if diff_moves else False
                )
                report["new_total"] = abs(move.amount_total_signed)
                report["new_tax"] = abs(move.amount_tax_signed)
                report["new_residual"] = abs(move.amount_residual_signed)
                return report
        report["action"] = "already_ok"
        return report

    if counterpart_ids:
        term_lines.remove_move_reconcile()
        term_lines.invalidate_recordset()
        counterparts = env["account.move.line"].browse(counterpart_ids).exists()
        if not counterparts:
            raise ValueError(
                "Se perdieron contrapartidas de cobro al desconciliar %s; abortado"
                % move.name
            )

    tax_lines = move.line_ids.filtered("tax_line_id")
    tax_matched = tax_lines.filtered(
        lambda line: line.matched_debit_ids or line.matched_credit_ids
    )
    tax_counterparts = env["account.move.line"]
    for line in tax_matched:
        tax_counterparts |= line.matched_debit_ids.mapped("debit_move_id")
        tax_counterparts |= line.matched_credit_ids.mapped("credit_move_id")
    tax_counterpart_ids = tax_counterparts.ids
    if tax_matched:
        tax_matched.remove_move_reconcile()

    product_lines = move.line_ids.filtered(lambda line: line.display_type == "product")
    if (
        float_compare(
            abs(printed_base - current_base),
            DIFF_THRESHOLD,
            precision_rounding=company_currency.rounding,
        )
        >= 0
        and product_lines
    ):
        _scale_balances(product_lines, printed_base)

    tax_lines = move.line_ids.filtered("tax_line_id")
    _scale_balances(tax_lines, printed_tax)
    _scale_tax_base(tax_lines, printed_base)
    term_lines = move.line_ids.filtered(lambda line: line.display_type == "payment_term")
    _scale_balances(term_lines, printed_total)
    _fix_move_imbalance(move)
    _sync_product_company_amounts(move)

    move.invalidate_recordset()
    move.line_ids.invalidate_recordset()
    env.flush_all()

    if counterparts:
        counterparts = _align_payment_account(term_lines, counterparts)
        _reconcile_by_account(
            term_lines.filtered(lambda line: not line.reconciled),
            counterparts.filtered(lambda line: not line.reconciled),
        )

    if tax_counterpart_ids:
        tax_lines = move.line_ids.filtered("tax_line_id")
        tax_pay = env["account.move.line"].browse(tax_counterpart_ids).exists()
        _reconcile_by_account(
            tax_lines.filtered(lambda line: not line.reconciled),
            tax_pay.filtered(lambda line: not line.reconciled),
        )

    move.invalidate_recordset()
    move.line_ids.invalidate_recordset()
    counterparts.invalidate_recordset()
    env.flush_all()

    if paid_like:
        # Residual puede quedar en el vencimiento (total máquina mayor) o en el
        # cobro (total máquina menor). Ambos se cubren con EXCH y se concilian.
        to_clear = _open_term_lines(move)
        company_currency = move.company_currency_id
        payment_open = counterparts.filtered(
            lambda line: not line.reconciled
            and (
                not float_is_zero(
                    line.amount_residual,
                    precision_rounding=company_currency.rounding,
                )
                or (
                    line.currency_id
                    and not float_is_zero(
                        line.amount_residual_currency,
                        precision_rounding=line.currency_id.rounding,
                    )
                )
            )
        )
        to_clear |= payment_open
        if to_clear:
            diff_moves, kind = _create_and_reconcile_difference(move, to_clear)
            report["diff_entry"] = kind or False
            report["diff_move"] = (
                ", ".join(diff_moves.mapped("name")) if diff_moves else False
            )
        else:
            report["diff_entry"] = False
    else:
        report["diff_entry"] = "keep_residual"

    move.invalidate_recordset()
    report["action"] = "aligned"
    report["new_total"] = abs(move.amount_total_signed)
    report["new_tax"] = abs(move.amount_tax_signed)
    report["new_residual"] = abs(move.amount_residual_signed)
    return report


domain = [
    ("move_type", "in", ("out_invoice", "out_refund")),
    ("state", "=", "posted"),
    ("l10n_ve_invoice_original_printed", "=", True),
]
if MOVE_NAMES:
    domain.append(("name", "in", list(MOVE_NAMES)))
else:
    domain.append(("currency_id", "!=", env.company.currency_id.id))
if DATE_FROM:
    domain.append(("invoice_date", ">=", DATE_FROM))
if DATE_TO:
    domain.append(("invoice_date", "<=", DATE_TO))

moves = env["account.move"].search(domain, order="invoice_date, name")
print(
    "Modo: %s | facturas candidatas: %s"
    % ("APPLY" if APPLY else "DRY-RUN", len(moves))
)

results = []
errors = []
skipped_no_audit = 0
for move in moves:
    audit_lines = _audit_product_lines(move)
    if not audit_lines:
        skipped_no_audit += 1
        continue
    try:
        with env.cr.savepoint():
            results.append(_align_move(move, audit_lines, dry_run=not APPLY))
    except Exception as exc:
        errors.append({"name": move.name, "error": str(exc)})
        print("ERROR %s: %s" % (move.name, exc))

by_action = defaultdict(int)
by_catalog = defaultdict(int)
by_diff = defaultdict(int)
for row in results:
    by_action[row["action"]] += 1
    if row["action"] in ("would_align", "aligned"):
        catalog = "pagado" if row.get("paid_like") else "abierta"
        by_catalog[catalog] += 1
        if row.get("diff_entry"):
            by_diff[row["diff_entry"]] += 1
        print(
            "%(name)s fiscal=%(fiscal)s pay=%(payment_state)s residual=%(residual).2f "
            "paid_like=%(paid_like)s odoo=%(current_total).2f printed=%(printed_total).2f "
            "delta=%(delta_total)+.2f action=%(action)s diff=%(diff_entry)s"
            % row
            + (
                (" exch=%s" % row["diff_move"])
                if row.get("diff_move")
                else ""
            )
        )

print("---")
print("sin auditoría de líneas:", skipped_no_audit)
print("por acción:", dict(by_action))
print("mal catalogo (pagado= paid|in_payment residual 0):", dict(by_catalog))
print("asiento diferencia previsto:", dict(by_diff))
print("errores:", len(errors))
for row in errors[:20]:
    print("  %(name)s: %(error)s" % row)
if APPLY:
    env.cr.commit()
    print("CONFIRMADO (commit)")
else:
    env.cr.rollback()
    print("DRY-RUN (rollback). Revisa y ejecuta con APPLY=True")
