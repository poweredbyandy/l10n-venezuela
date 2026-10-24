# Part of Odoo. See LICENSE file for full copyright and licensing details.

from lxml import etree

from odoo import api, fields, models
from odoo.tools import float_is_zero


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_tax_totals_editable = fields.Boolean(
        compute="_compute_l10n_ve_tax_totals_editable",
    )

    @api.depends("state", "move_type")
    @api.depends_context("uid")
    def _compute_l10n_ve_tax_totals_editable(self):
        for move in self:
            move.l10n_ve_tax_totals_editable = move._l10n_ve_can_edit_tax_totals()

    @api.depends_context("uid")
    @api.depends("state")
    def _compute_tax_totals(self):
        res = super()._compute_tax_totals()
        for move in self:
            if not move.tax_totals or not move.is_invoice(include_receipts=True):
                continue
            totals = dict(move.tax_totals)
            totals["can_edit_tax_totals"] = move._l10n_ve_can_edit_tax_totals()
            move.tax_totals = totals
        return res

    def write(self, vals):
        manual_tax_totals = isinstance(vals.get("tax_totals"), dict) and bool(
            vals["tax_totals"].get("manual_edit")
        )
        res = super().write(vals)
        if manual_tax_totals:
            self._l10n_ve_flush_pending_tax_totals_edits()
            self.invalidate_recordset(["tax_totals"])
            self._compute_tax_totals()
        return res

    def _l10n_ve_can_edit_tax_totals(self):
        self.ensure_one()
        return bool(
            self.state == "draft"
            and self.is_invoice(include_receipts=True)
            and self.env.user.has_group(
                "l10n_ve_tax_totals_manual.group_l10n_ve_tax_totals_manual"
            )
        )

    @api.model
    def _get_view(self, view_id=None, view_type="form", **options):
        arch, view = super()._get_view(view_id, view_type, **options)
        if view_type != "form":
            return arch, view
        for node in arch.xpath("//field[@name='tax_totals']"):
            readonly = node.get("readonly")
            if readonly and "l10n_ve_tax_totals_editable" not in readonly:
                node.set(
                    "readonly",
                    f"({readonly}) and not l10n_ve_tax_totals_editable",
                )
            if not arch.xpath("//field[@name='l10n_ve_tax_totals_editable']"):
                helper = etree.Element("field")
                helper.set("name", "l10n_ve_tax_totals_editable")
                helper.set("invisible", "1")
                node.addprevious(helper)
        return arch, view

    def _l10n_ve_tax_totals_manual_kinds(self):
        return {
            "subtotal_currency",
            "subtotal_company",
            "gross_currency",
            "gross_company",
            "tax_company",
            "total_currency",
            "total_company",
            "discount_currency",
            "discount_company",
        }

    def _l10n_ve_pending_tax_totals_state(self):
        cursor = self.env.cr
        pending = getattr(cursor, "_l10n_ve_tax_totals_pending_edits", None)
        seen = getattr(cursor, "_l10n_ve_tax_totals_pending_keys", None)
        if pending is None:
            pending = []
            cursor._l10n_ve_tax_totals_pending_edits = pending
        if seen is None:
            seen = set()
            cursor._l10n_ve_tax_totals_pending_keys = seen
        return pending, seen

    def _inverse_tax_totals(self):
        pending, seen = self._l10n_ve_pending_tax_totals_state()
        for move in self:
            totals = move.tax_totals
            if not isinstance(totals, dict):
                continue
            edit = totals.pop("manual_edit", None)
            if not edit:
                continue
            key = (
                move.id,
                edit.get("kind"),
                edit.get("new_value"),
                edit.get("tax_group_id"),
                edit.get("subtotal_name"),
            )
            if key in seen:
                continue
            seen.add(key)
            pending.append((move, edit))
        return super()._inverse_tax_totals()

    def _l10n_ve_flush_pending_tax_totals_edits(self):
        pending, seen = self._l10n_ve_pending_tax_totals_state()
        edits = [
            (self.browse(move.id), edit)
            for move, edit in pending
            if move.id in self.ids
        ]
        self.env.cr._l10n_ve_tax_totals_pending_edits = [
            item for item in pending if item[0].id not in self.ids
        ]
        if not edits:
            return
        if seen is not None:
            for move, edit in edits:
                seen.discard(
                    (
                        move.id,
                        edit.get("kind"),
                        edit.get("new_value"),
                        edit.get("tax_group_id"),
                        edit.get("subtotal_name"),
                    )
                )
        discount_edits = []
        other_edits = []
        for move, edit in edits:
            kind = (edit or {}).get("kind") or ""
            if kind.startswith("discount"):
                discount_edits.append((move, edit))
            else:
                other_edits.append((move, edit))
        container = {"records": self}
        with self._check_balanced(container):
            if other_edits:
                with self._sync_dynamic_lines(container):
                    for move, edit in other_edits:
                        move._l10n_ve_apply_tax_totals_manual_edit(edit)
            for move, edit in discount_edits:
                move._l10n_ve_apply_tax_totals_manual_edit(edit)

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        base_line = super()._prepare_product_base_line_for_taxes_computation(
            product_line
        )
        if product_line.l10n_ve_manual_untaxed_currency_active:
            base_line["manual_total_excluded_currency"] = (
                product_line.l10n_ve_manual_untaxed_currency
            )
        if product_line.l10n_ve_manual_untaxed_company_active:
            base_line["manual_total_excluded"] = (
                product_line.l10n_ve_manual_untaxed_company
            )
        return base_line

    def _l10n_ve_apply_tax_totals_manual_edit(self, edit):
        """Force a tax-totals amount and the journal items behind it.

        The total edit adjusts the tax (or the base when the invoice has no
        tax) so the typed total is the one posted on the receivable line.
        """
        self.ensure_one()
        if not self._l10n_ve_can_edit_tax_totals() or not isinstance(edit, dict):
            return
        kind = edit.get("kind")
        if kind not in self._l10n_ve_tax_totals_manual_kinds():
            return
        try:
            new_value = float(edit.get("new_value"))
        except (TypeError, ValueError):
            return
        signature = (
            self.id,
            kind,
            edit.get("tax_group_id"),
            edit.get("subtotal_name"),
            round(new_value, 6),
        )
        done = getattr(self.env, "_l10n_ve_tax_totals_manual_edits", None)
        if done is None:
            done = set()
            self.env._l10n_ve_tax_totals_manual_edits = done
        if signature in done:
            return
        done.add(signature)
        edit = dict(edit, new_value=new_value)
        live = self._l10n_ve_live_tax_totals()
        handler = getattr(self, f"_l10n_ve_manual_edit_{kind}", None)
        if handler:
            handler(edit, live)
        self.env.add_to_compute(self.line_ids._fields["debit"], self.line_ids)
        self.env.add_to_compute(self.line_ids._fields["credit"], self.line_ids)
        self._compute_amount()

    def _l10n_ve_live_tax_totals(self):
        self.ensure_one()
        base_lines, _tax_lines = self._get_rounded_base_and_tax_lines()
        totals = self.env["account.tax"]._get_tax_totals_summary(
            base_lines=base_lines,
            currency=self.currency_id,
            company=self.company_id,
            cash_rounding=self.invoice_cash_rounding_id,
        )
        applier = getattr(
            self.env["account.tax"],
            "_l10n_ve_apply_global_discount_to_tax_totals",
            None,
        )
        if applier and self.country_code == "VE":
            totals = applier(self, totals)
        align = getattr(self, "_l10n_ve_align_refund_tax_totals_to_accounting", None)
        if align:
            totals = align(totals)
        return totals or {}

    def _l10n_ve_live_subtotal(self, live, name):
        subtotals = (live or {}).get("subtotals") or []
        for subtotal in subtotals:
            if name and subtotal.get("name") == name:
                return subtotal
        if len(subtotals) == 1:
            return subtotals[0]
        return None

    def _l10n_ve_manual_product_lines(self):
        lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        if "l10n_ve_global_discount_line" in lines._fields:
            lines = lines.filtered(lambda line: not line.l10n_ve_global_discount_line)
        getter = getattr(self, "_l10n_ve_get_product_discount_lines", None)
        if getter:
            lines = lines - getter()
        return lines

    def _l10n_ve_manual_discount_lines(self):
        line_model = self.env["account.move.line"]
        if "l10n_ve_global_discount_line" not in line_model._fields:
            return line_model
        return self.line_ids.filtered(
            lambda line: line.l10n_ve_global_discount_line
            or line.display_type == "global_discount"
        )

    def _l10n_ve_lines_for_subtotal(self, subtotal):
        lines = self._l10n_ve_manual_product_lines()
        if not subtotal:
            return lines
        group_ids = {
            group.get("id")
            for group in subtotal.get("tax_groups") or []
            if group.get("id")
        }
        if not group_ids:
            return lines
        matched = lines.filtered(
            lambda line: set(line.tax_ids.tax_group_id.ids) & group_ids
        )
        return matched or lines

    def _l10n_ve_discount_currency_amount(self):
        lines = self._l10n_ve_manual_discount_lines()
        if lines:
            return abs(sum(lines.mapped("amount_currency")))
        getter = getattr(self, "_l10n_ve_get_product_discount_lines", None)
        if getter:
            return abs(sum(getter().mapped("price_subtotal")))
        return 0.0

    def _l10n_ve_discount_company_amount(self):
        lines = self._l10n_ve_manual_discount_lines()
        if lines:
            return abs(sum(lines.mapped("balance")))
        getter = getattr(self, "_l10n_ve_get_product_discount_lines", None)
        if getter:
            return abs(sum(getter().mapped("balance")))
        return 0.0

    def _l10n_ve_split_manual_amount(self, amount, weights, currency):
        self.ensure_one()
        if not weights:
            return []
        if len(weights) == 1:
            return [currency.round(amount)]
        total_weight = sum(weights)
        if currency.is_zero(total_weight):
            return [currency.round(amount)] + [0.0] * (len(weights) - 1)
        parts = []
        accumulated = 0.0
        for weight in weights[:-1]:
            part = currency.round(amount * weight / total_weight)
            parts.append(part)
            accumulated += part
        parts.append(currency.round(amount - accumulated))
        return parts

    def _l10n_ve_scale_product_untaxed_currency(self, lines, target):
        currency = self.currency_id
        lines = lines.exists() if lines else lines
        if not lines:
            return
        amounts = [abs(line.price_subtotal) for line in lines]
        current = sum(amounts)
        if currency.is_zero(current):
            line = lines[0]
            quantity = line.quantity or 1.0
            factor = 1.0 - (line.discount or 0.0) / 100.0
            denominator = quantity * factor or 1.0
            line.price_unit = target / denominator
            return
        if currency.is_zero(target - current):
            return
        parts = self._l10n_ve_split_manual_amount(target, amounts, currency)
        for line, part, current_line in zip(lines, parts, amounts, strict=False):
            if currency.is_zero(current_line):
                continue
            line.price_unit = line.price_unit * (part / current_line)

    def _l10n_ve_set_product_company_gross(self, lines, gross):
        currency = self.company_currency_id
        if not lines:
            return
        amounts = [abs(line.balance) for line in lines]
        current = sum(amounts)
        if currency.is_zero(current):
            parts = [currency.round(gross)] + [0.0] * (len(lines) - 1)
        else:
            parts = self._l10n_ve_split_manual_amount(gross, amounts, currency)
        for line, part in zip(lines, parts, strict=False):
            if currency.is_zero(line.balance):
                line.balance = self.direction_sign * part
            elif line.balance < 0:
                line.balance = -part
            else:
                line.balance = part
            line.l10n_ve_manual_untaxed_company = part
            line.l10n_ve_manual_untaxed_company_active = True
            line.l10n_ve_manual_balance_active = True

    def _l10n_ve_force_company_tax_base(self, new_base):
        tax_lines = self.line_ids.filtered("tax_line_id")
        if not tax_lines:
            return
        grouped = {}
        empty_lines = self.env["account.move.line"]
        for line in tax_lines:
            group_id = line.tax_line_id.tax_group_id.id
            grouped.setdefault(group_id, empty_lines)
            grouped[group_id] |= line
        currents = [
            abs(sum(lines.mapped("tax_base_amount"))) for lines in grouped.values()
        ]
        parts = self._l10n_ve_split_manual_amount(
            new_base, currents, self.company_currency_id
        )
        for lines, part in zip(grouped.values(), parts, strict=False):
            total = sum(lines.mapped("tax_base_amount"))
            target = part if total >= 0 else -part
            if float_is_zero(
                total, precision_rounding=self.company_currency_id.rounding
            ):
                lines[0].tax_base_amount = target
                continue
            factor = target / total
            for line in lines:
                line.tax_base_amount = line.tax_base_amount * factor

    def _l10n_ve_tax_lines_for_group(self, tax_group_id):
        return self.line_ids.filtered(
            lambda line: line.tax_line_id
            and line.tax_line_id.tax_group_id.id == tax_group_id
        )

    def _l10n_ve_add_display_delta_to_tax_currency(self, delta):
        currency = self.currency_id
        if currency.is_zero(delta):
            return
        tax_lines = self.line_ids.filtered("tax_repartition_line_id")
        if not tax_lines:
            lines = self._l10n_ve_manual_product_lines()
            current = sum(abs(line.price_subtotal) for line in lines)
            self._l10n_ve_scale_product_untaxed_currency(lines, current + delta)
            return
        line = max(tax_lines, key=lambda tax_line: abs(tax_line.amount_currency))
        line.amount_currency += delta * self.direction_sign
        if not line.l10n_ve_manual_balance_active:
            rate = line.currency_rate or self.invoice_currency_rate or 1.0
            if rate:
                line.balance = self.company_currency_id.round(
                    line.amount_currency / rate
                )

    def _l10n_ve_add_display_delta_to_tax_company(self, delta):
        currency = self.company_currency_id
        if currency.is_zero(delta):
            return
        tax_lines = self.line_ids.filtered("tax_repartition_line_id")
        if not tax_lines:
            lines = self._l10n_ve_manual_product_lines()
            gross = sum(abs(line.balance) for line in lines) + delta
            self._l10n_ve_set_product_company_gross(lines, gross)
            self._l10n_ve_force_company_tax_base(
                max(gross - self._l10n_ve_discount_company_amount(), 0.0)
            )
            return
        line = max(tax_lines, key=lambda tax_line: abs(tax_line.balance))
        line.balance += delta * self.direction_sign
        line.l10n_ve_manual_balance_active = True

    def _l10n_ve_manual_edit_subtotal_currency(self, edit, live):
        subtotal = self._l10n_ve_live_subtotal(live, edit.get("subtotal_name"))
        current = (subtotal or {}).get("base_amount_currency") or 0.0
        new_value = edit["new_value"]
        if self.currency_id.is_zero(new_value - current):
            return
        lines = self._l10n_ve_lines_for_subtotal(subtotal)
        current_gross = sum(abs(line.price_subtotal) for line in lines)
        self._l10n_ve_scale_product_untaxed_currency(
            lines, current_gross + (new_value - current)
        )

    def _l10n_ve_manual_edit_subtotal_company(self, edit, live):
        subtotal = self._l10n_ve_live_subtotal(live, edit.get("subtotal_name"))
        current = (subtotal or {}).get("base_amount") or 0.0
        new_value = edit["new_value"]
        if self.company_currency_id.is_zero(new_value - current):
            return
        lines = self._l10n_ve_lines_for_subtotal(subtotal)
        self._l10n_ve_set_product_company_gross(
            lines, new_value + self._l10n_ve_discount_company_amount()
        )
        self._l10n_ve_force_company_tax_base(new_value)

    def _l10n_ve_manual_edit_gross_currency(self, edit, live):
        lines = self._l10n_ve_manual_product_lines()
        current = live.get("l10n_ve_subtotal_gross_currency")
        if current is None:
            current = sum(abs(line.price_subtotal) for line in lines)
        new_value = edit["new_value"]
        if self.currency_id.is_zero(new_value - current):
            return
        self._l10n_ve_scale_product_untaxed_currency(lines, new_value)

    def _l10n_ve_manual_edit_gross_company(self, edit, live):
        lines = self._l10n_ve_manual_product_lines()
        new_value = edit["new_value"]
        current = live.get("l10n_ve_subtotal_gross")
        if current is None:
            current = sum(abs(line.balance) for line in lines)
        if self.company_currency_id.is_zero(new_value - current):
            return
        self._l10n_ve_set_product_company_gross(lines, new_value)
        self._l10n_ve_force_company_tax_base(
            max(new_value - self._l10n_ve_discount_company_amount(), 0.0)
        )

    def _l10n_ve_manual_edit_tax_company(self, edit, live):
        tax_group_id = edit.get("tax_group_id")
        lines = self._l10n_ve_tax_lines_for_group(tax_group_id)
        if not lines:
            return
        current = abs(sum(lines.mapped("balance")))
        new_value = edit["new_value"]
        if self.company_currency_id.is_zero(new_value - current):
            return
        line = lines[0]
        line.balance += (new_value - current) * self.direction_sign
        line.l10n_ve_manual_balance_active = True

    def _l10n_ve_manual_edit_total_currency(self, edit, live):
        current = live.get("total_amount_currency") or 0.0
        self._l10n_ve_add_display_delta_to_tax_currency(edit["new_value"] - current)

    def _l10n_ve_manual_edit_total_company(self, edit, live):
        current = live.get("total_amount") or 0.0
        self._l10n_ve_add_display_delta_to_tax_company(edit["new_value"] - current)

    def _l10n_ve_manual_edit_discount_currency(self, edit, live):
        new_value = abs(edit["new_value"])
        current = live.get("l10n_ve_global_discount_amount_currency") or 0.0
        if self.currency_id.is_zero(new_value - current):
            return
        discounts = self.l10n_ve_global_discount_ids
        if discounts:
            self._l10n_ve_manual_discount_lines().write(
                {"l10n_ve_manual_balance_active": False}
            )
            percentages = discounts.filtered(
                lambda discount: discount.discount_type == "percentage"
            )
            fixed = discounts.filtered(
                lambda discount: discount.discount_type != "percentage"
            ).sorted("id")
            ordered = percentages + fixed
            amounts = {
                line["id"]: line.get("amount") or 0.0
                for line in live.get("l10n_ve_global_discount_lines") or []
            }
            last = ordered[-1]
            others = sum(amounts.get(discount.id, 0.0) for discount in ordered[:-1])
            last.with_context(l10n_ve_skip_global_discount_access_check=True).write(
                {
                    "discount_type": "fixed",
                    "amount_base": "untaxed",
                    "discount_percentage": 0.0,
                    "amount": max(self.currency_id.round(new_value - others), 0.0),
                }
            )
            return
        getter = getattr(self, "_l10n_ve_get_product_discount_lines", None)
        lines = getter() if getter else self.env["account.move.line"]
        if lines:
            self._l10n_ve_scale_product_untaxed_currency(lines, new_value)

    def _l10n_ve_manual_edit_discount_company(self, edit, live):
        new_value = abs(edit["new_value"])
        lines = self._l10n_ve_manual_discount_lines()
        if not lines:
            getter = getattr(self, "_l10n_ve_get_product_discount_lines", None)
            lines = getter() if getter else lines
        if not lines:
            return
        currency = self.company_currency_id
        current = abs(sum(lines.mapped("balance")))
        if currency.is_zero(new_value - current):
            return
        delta = new_value - current
        line = lines[0]
        if currency.is_zero(line.balance):
            line.balance = -self.direction_sign * new_value
        elif line.balance < 0:
            line.balance -= delta
        else:
            line.balance += delta
        line.l10n_ve_manual_balance_active = True
        gross = sum(
            abs(product.balance) for product in self._l10n_ve_manual_product_lines()
        )
        self._l10n_ve_force_company_tax_base(max(gross - new_value, 0.0))

    def _l10n_ve_pre_global_product_line_update(self, base_line, to_update):
        to_update = super()._l10n_ve_pre_global_product_line_update(
            base_line, to_update
        )
        record = base_line.get("record")
        if not record or not record.l10n_ve_manual_balance_active:
            return to_update
        to_update = dict(to_update)
        to_update["balance"] = record.balance
        if not record.l10n_ve_manual_untaxed_currency_active:
            to_update["amount_currency"] = record.amount_currency
        return to_update

    def _l10n_ve_apply_tax_results_writes(self, tax_results, MoveLine):
        manual_lines = self.line_ids.filtered("l10n_ve_manual_balance_active")
        saved_balance = {line.id: line.balance for line in manual_lines}
        saved_tax_base = {}
        if manual_lines.filtered(lambda line: line.display_type == "product"):
            for line in self.line_ids.filtered("tax_line_id"):
                saved_tax_base[line.id] = line.tax_base_amount
        result = super()._l10n_ve_apply_tax_results_writes(tax_results, MoveLine)
        for line in self.line_ids:
            balance = saved_balance.get(line.id)
            if balance is not None and line.balance != balance:
                line.with_context(
                    l10n_ve_skip_discount_refresh=True,
                    l10n_ve_keep_manual_tax_totals=True,
                ).write({"balance": balance})
            tax_base = saved_tax_base.get(line.id)
            if tax_base is not None and line.tax_base_amount != tax_base:
                line.tax_base_amount = tax_base
        return result

    def _l10n_ve_needed_global_discount_journal_values(
        self, allocations, discount_account
    ):
        needed = super()._l10n_ve_needed_global_discount_journal_values(
            allocations, discount_account
        )
        for key, values in needed.items():
            tax_ids = set(key.get("tax_ids") or ())
            manual_lines = self.line_ids.filtered(
                lambda line, tax_ids=tax_ids: line.l10n_ve_global_discount_line
                and line.l10n_ve_manual_balance_active
                and set(line.l10n_ve_global_discount_tax_ids.ids) == tax_ids
            )
            if manual_lines:
                values["balance"] = sum(manual_lines.mapped("balance"))
        return needed
