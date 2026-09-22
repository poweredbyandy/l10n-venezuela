from collections import defaultdict
from copy import deepcopy

from odoo import _, api, fields, models
from odoo.fields import Command
from odoo.tools import float_compare, float_is_zero, float_round


# pylint: disable=consider-merging-classes-inherited
class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_requires_refund_company_currency(self):
        """Credit notes keep the invoice currency; do not force company currency."""
        self.ensure_one()
        return False

    def _l10n_ve_document_base_amount(self, line):
        qty = abs(line.quantity or 0.0)
        discount_factor = 1.0 - (line.discount or 0.0) / 100.0
        return qty * (line.price_unit or 0.0) * discount_factor

    def _l10n_ve_company_subtotal_unrounded_from_origin_line(self, line):
        raw_base = self._l10n_ve_document_base_amount(line)
        if line.currency_id == line.company_currency_id:
            return raw_base
        date = (
            line.move_id.invoice_date
            or line.move_id.date
            or fields.Date.context_today(self)
        )
        return line.currency_id._convert(
            raw_base,
            line.company_currency_id,
            line.company_id,
            date,
            round=False,
        )

    def _l10n_ve_tax_price_unit_from_origin_line(self, line):
        if line.currency_id == line.company_currency_id:
            return line.price_unit
        qty = abs(line.quantity or 0.0)
        if not qty:
            return line.price_unit_company_currency
        discount_factor = 1.0 - (line.discount or 0.0) / 100.0
        if discount_factor <= 0.0:
            return 0.0
        subtotal = self._l10n_ve_company_subtotal_unrounded_from_origin_line(line)
        prec = self.env["decimal.precision"].precision_get("Product Price")
        prec = max(prec, 4)
        return float_round(subtotal / discount_factor / qty, precision_digits=prec)

    def _l10n_ve_company_price_unit_from_origin_line(self, line):
        if line.currency_id == line.company_currency_id:
            return line.price_unit
        qty = abs(line.quantity or 0.0)
        if not qty:
            return line.price_unit_company_currency
        discount_factor = 1.0 - (line.discount or 0.0) / 100.0
        if discount_factor <= 0.0:
            return 0.0
        subtotal = self._l10n_ve_company_subtotal_unrounded_from_origin_line(line)
        prec = self.env["decimal.precision"].precision_get("Product Price")
        return float_round(subtotal / discount_factor / qty, precision_digits=prec)

    def _l10n_ve_company_subtotal_from_origin_line(self, line):
        if line.currency_id == line.company_currency_id:
            return abs(line.price_subtotal)
        return line.price_subtotal_currency

    def _l10n_ve_refund_should_use_unrounded_tax_base(self):
        self.ensure_one()
        if self.country_code != self.env.ref("base.ve").code:
            return False
        if self.move_type != "out_refund":
            return False
        if self.currency_id != self.company_currency_id:
            return False
        origin = self.reversed_entry_id
        if not origin or origin.currency_id == origin.company_currency_id:
            return False
        if not self._l10n_ve_requires_refund_company_currency():
            return False
        return True

    def _l10n_ve_origin_line_for_tax_base(self, product_line):
        origin = self.reversed_entry_id
        if not origin:
            return self.env["account.move.line"]
        origin_products = origin.invoice_line_ids.filtered(
            lambda line: line.display_type == product_line.display_type
        ).sorted(lambda line: (line.sequence, line.id))
        credit_products = self.invoice_line_ids.filtered(
            lambda line: line.display_type == product_line.display_type
        ).sorted(lambda line: (line.sequence, line.id))
        if len(origin_products) == len(credit_products) and all(
            (origin_line.product_id.id or 0) == (credit_line.product_id.id or 0)
            and tuple(sorted(origin_line.tax_ids.ids))
            == tuple(sorted(credit_line.tax_ids.ids))
            for origin_line, credit_line in zip(
                origin_products, credit_products, strict=False
            )
        ):
            for origin_line, credit_line in zip(
                origin_products, credit_products, strict=False
            ):
                if credit_line == product_line:
                    return origin_line
        candidates = origin_products.filtered(
            lambda line: (line.product_id.id or 0) == (product_line.product_id.id or 0)
            and tuple(sorted(line.tax_ids.ids))
            == tuple(sorted(product_line.tax_ids.ids))
        )
        if len(candidates) == 1:
            return candidates
        if not candidates:
            return self.env["account.move.line"]
        same_seq = candidates.filtered(
            lambda line: line.sequence == product_line.sequence
        )
        if len(same_seq) == 1:
            return same_seq
        unused = candidates
        for credit_line in credit_products:
            if credit_line == product_line:
                break
            matched = unused.filtered(
                lambda line, credit_line=credit_line: (line.product_id.id or 0)
                == (credit_line.product_id.id or 0)
                and tuple(sorted(line.tax_ids.ids))
                == tuple(sorted(credit_line.tax_ids.ids))
            )[:1]
            unused -= matched
        return unused[:1]

    def _get_rounded_base_and_tax_lines(self, round_from_tax_lines=True):
        if self._l10n_ve_refund_should_use_unrounded_tax_base():
            self = self.with_context(l10n_ve_unrounded_tax_base=True)
        return super()._get_rounded_base_and_tax_lines(
            round_from_tax_lines=round_from_tax_lines
        )

    def _prepare_product_base_line_for_taxes_computation(self, product_line):
        base_line = super()._prepare_product_base_line_for_taxes_computation(
            product_line
        )
        if not self.env.context.get("l10n_ve_unrounded_tax_base"):
            return base_line
        if not self._l10n_ve_refund_should_use_unrounded_tax_base():
            return base_line
        if product_line.display_type not in ("product", "cogs"):
            return base_line
        origin_line = self._l10n_ve_origin_line_for_tax_base(product_line)
        if not origin_line:
            return base_line
        origin_tax_pu = self._l10n_ve_tax_price_unit_from_origin_line(origin_line)
        origin_pub_pu = self._l10n_ve_company_price_unit_from_origin_line(origin_line)
        credit_pu = product_line.price_unit
        price_prec = self.env["decimal.precision"].precision_get("Product Price")
        if origin_pub_pu and float_compare(
            credit_pu, origin_pub_pu, precision_digits=price_prec
        ):
            base_line["price_unit"] = origin_tax_pu * (credit_pu / origin_pub_pu)
        else:
            base_line["price_unit"] = origin_tax_pu
        return base_line

    def _l10n_ve_refund_line_uses_origin_company_amounts(
        self, origin_line, credit_line
    ):
        company_cur = credit_line.company_currency_id
        origin_pu = self._l10n_ve_company_price_unit_from_origin_line(origin_line)
        price_prec = self.env["decimal.precision"].precision_get("Product Price")
        qty_prec = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        same_qty = not float_compare(
            abs(credit_line.quantity or 0.0),
            abs(origin_line.quantity or 0.0),
            precision_digits=qty_prec,
        )
        if origin_pu and not float_compare(
            credit_line.price_unit,
            origin_pu,
            precision_digits=price_prec,
        ):
            return True
        if credit_line.currency_id == origin_line.currency_id and not float_compare(
            origin_line.price_unit,
            credit_line.price_unit,
            precision_rounding=origin_line.currency_id.rounding,
        ):
            return True
        if origin_line.currency_id and not origin_line.currency_id.is_zero(
            origin_line.amount_currency
        ):
            legacy_pu = company_cur.round(
                origin_line.price_unit
                * (abs(origin_line.balance) / abs(origin_line.amount_currency))
            )
            if legacy_pu and not float_compare(
                credit_line.price_unit,
                legacy_pu,
                precision_rounding=company_cur.rounding,
            ):
                return True
        if credit_line.currency_id == company_cur:
            if not same_qty:
                return False
            if origin_pu and not float_compare(
                credit_line.price_unit,
                origin_pu,
                precision_digits=price_prec,
            ):
                return True
            return False
        return False

    def _l10n_ve_company_price_unit_from_refund_line(self, origin_line, credit_line):
        origin_pu = self._l10n_ve_company_price_unit_from_origin_line(origin_line)
        origin_currency = origin_line.currency_id
        if origin_currency.is_zero(origin_line.price_unit):
            return origin_pu
        if credit_line.currency_id != origin_currency:
            return origin_pu
        if not float_compare(
            origin_line.price_unit,
            credit_line.price_unit,
            precision_rounding=origin_currency.rounding,
        ):
            return origin_pu
        return origin_pu * (credit_line.price_unit / origin_line.price_unit)

    def _l10n_ve_refund_line_pair_key(self, line, company=False):
        if line.display_type in ("product", "cogs"):
            if company:
                match_key = self._l10n_ve_credit_note_line_company_match_key(line)
            else:
                match_key = self._l10n_ve_credit_note_line_match_key(line)
            return (line.display_type,) + match_key
        return (line.display_type,)

    def _l10n_ve_refund_line_product_pair_key(self, line):
        if line.display_type in ("product", "cogs"):
            return (
                line.display_type,
                line.product_id.id or 0,
                tuple(sorted(line.tax_ids.ids)),
            )
        return (line.display_type,)

    def _l10n_ve_refund_first_unused_origin_line(self, queue, used_origin_ids):
        for origin_line in queue:
            if origin_line.id not in used_origin_ids:
                return origin_line
        return self.env["account.move.line"]

    def _l10n_ve_refund_origin_credit_line_pairs(self, origin):
        orig_lines = origin.invoice_line_ids.sorted(
            lambda line: (line.sequence, line.id)
        )
        cred_lines = self.invoice_line_ids.sorted(lambda line: (line.sequence, line.id))
        currency_queues = defaultdict(list)
        company_queues = defaultdict(list)
        product_queues = defaultdict(list)
        for origin_line in orig_lines:
            currency_queues[self._l10n_ve_refund_line_pair_key(origin_line)].append(
                origin_line
            )
            company_queues[
                self._l10n_ve_refund_line_pair_key(origin_line, company=True)
            ].append(origin_line)
            product_queues[
                self._l10n_ve_refund_line_product_pair_key(origin_line)
            ].append(origin_line)
        pairs = []
        used_origin_ids = set()
        for credit_line in cred_lines:
            origin_line = self._l10n_ve_refund_first_unused_origin_line(
                currency_queues.get(
                    self._l10n_ve_refund_line_pair_key(credit_line), []
                ),
                used_origin_ids,
            )
            if not origin_line:
                origin_line = self._l10n_ve_refund_first_unused_origin_line(
                    company_queues.get(
                        self._l10n_ve_refund_line_pair_key(credit_line, company=True),
                        [],
                    ),
                    used_origin_ids,
                )
            if not origin_line:
                origin_line = self._l10n_ve_refund_first_unused_origin_line(
                    product_queues.get(
                        self._l10n_ve_refund_line_product_pair_key(credit_line),
                        [],
                    ),
                    used_origin_ids,
                )
            if not origin_line:
                return None
            used_origin_ids.add(origin_line.id)
            pairs.append((origin_line, credit_line))
        return pairs

    def _l10n_ve_refund_convert_paired_line_cmd(self, origin_line, credit_line):
        if origin_line.display_type in ("product", "cogs"):
            return Command.update(
                credit_line.id,
                {
                    "price_unit": self._l10n_ve_company_price_unit_from_refund_line(
                        origin_line, credit_line
                    ),
                },
            )
        if origin_line.display_type in ("rounding", "discount", "global_discount"):
            return Command.update(
                credit_line.id,
                {
                    "amount_currency": self._l10n_ve_company_subtotal_from_origin_line(
                        origin_line
                    ),
                },
            )
        return None


    def _l10n_ve_lock_refund_invoice_currency_rate_from_origin(self):
        for move in self:
            origin = move.reversed_entry_id
            if (
                move.move_type != "out_refund"
                or not origin
                or move.currency_id == move.company_currency_id
                or origin.currency_id != move.currency_id
                or not origin.invoice_currency_rate
            ):
                continue
            origin_rate = origin.invoice_currency_rate
            if not float_compare(
                move.invoice_currency_rate,
                origin_rate,
                precision_digits=6,
            ):
                continue
            # Keep the origin rate even if invoice_date triggers a recompute.
            with move.env.protecting(
                [move._fields["invoice_currency_rate"]], move
            ):
                move.with_context(
                    check_move_validity=False,
                    l10n_ve_skip_refund_rate_lock=True,
                ).write({"invoice_currency_rate": origin_rate})
            move.invalidate_recordset(["l10n_ve_inverse_rate"])

    def _l10n_ve_force_refund_to_company_currency(self):
        """Keep refund currency; freeze origin rate and company balances instead."""
        ve_country = self.env.ref("base.ve").code
        for move in self:
            if (
                move.country_code != ve_country
                or move.move_type != "out_refund"
                or not move.reversed_entry_id
            ):
                continue
            move._l10n_ve_lock_refund_invoice_currency_rate_from_origin()
            move._l10n_ve_align_refund_company_amounts_to_origin()
        return super()._l10n_ve_force_refund_to_company_currency()

    def _l10n_ve_apply_company_currency_from_line_balances(self):
        self.ensure_one()
        cc = self.company_currency_id
        line_cmds = []
        for line in self.invoice_line_ids:
            if line.display_type in ("product", "cogs"):
                line_cmds.append(
                    Command.update(
                        line.id,
                        {
                            "price_unit": (
                                self._l10n_ve_company_price_unit_from_origin_line(line)
                            )
                        },
                    )
                )
            elif line.display_type in ("rounding", "discount", "global_discount"):
                line_cmds.append(
                    Command.update(
                        line.id,
                        {
                            "amount_currency": line.price_subtotal_currency
                            or abs(line.balance)
                        },
                    )
                )
        vals = {"currency_id": cc.id}
        if line_cmds:
            vals["invoice_line_ids"] = line_cmds
        self.write(vals)
        self.flush_recordset()
        self._l10n_ve_align_refund_company_amounts_to_origin()

    def _l10n_ve_copy_origin_tax_company_amounts(self):
        for move in self:
            move._l10n_ve_copy_origin_tax_company_amounts_on_move()
        return self

    def _l10n_ve_copy_origin_tax_company_amounts_on_move(self):
        self.ensure_one()
        origin = self.reversed_entry_id
        if not origin:
            return False
        orig_taxes = origin.line_ids.filtered(
            lambda line: line.display_type == "tax"
        ).sorted(lambda line: (line.tax_line_id.id or 0, line.id))
        cred_taxes = self.line_ids.filtered(
            lambda line: line.display_type == "tax"
        ).sorted(lambda line: (line.tax_line_id.id or 0, line.id))
        if len(orig_taxes) != len(cred_taxes):
            return False
        company_cur = self.company_currency_id
        same_currency = self.currency_id == origin.currency_id
        line_cmds = []
        for origin_line, credit_line in zip(orig_taxes, cred_taxes, strict=False):
            if origin_line.tax_line_id != credit_line.tax_line_id:
                return False
            sign = 1.0 if credit_line.balance >= 0.0 else -1.0
            amount = company_cur.round(abs(origin_line.balance)) * sign
            amount_currency = None
            if same_currency:
                amount_currency = self.currency_id.round(
                    abs(origin_line.amount_currency)
                ) * (1.0 if credit_line.amount_currency >= 0.0 else -1.0)
            command = self._l10n_ve_align_refund_balance_cmd(
                credit_line, amount, amount_currency=amount_currency
            )
            if command:
                line_cmds.append(command)
        if line_cmds:
            self.with_context(
                skip_invoice_sync=True,
                check_move_validity=False,
            ).write({"line_ids": line_cmds})
            self._l10n_ve_resync_refund_payment_term_after_tax_align()
        return True

    def _l10n_ve_resync_refund_payment_term_after_tax_align(self):
        self.ensure_one()
        term_lines = self.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        ).sorted(lambda line: (line.date_maturity or fields.Date.today(), line.id))
        if not term_lines:
            return
        company_cur = self.company_currency_id
        residual = company_cur.round(
            -sum((self.line_ids - term_lines).mapped("balance"))
        )
        current = company_cur.round(sum(term_lines.mapped("balance")))
        if not float_compare(
            current, residual, precision_rounding=company_cur.rounding
        ):
            return
        weights = [abs(line.balance) for line in term_lines]
        weight_sum = sum(weights)
        if company_cur.is_zero(weight_sum):
            weights = [1.0] * len(term_lines)
            weight_sum = float(len(term_lines))
        allocated = 0.0
        line_cmds = []
        last_index = len(term_lines) - 1
        for index, line in enumerate(term_lines):
            if index == last_index:
                amount = company_cur.round(residual - allocated)
            else:
                amount = company_cur.round(residual * (weights[index] / weight_sum))
                allocated += amount
            if float_compare(
                line.balance, amount, precision_rounding=company_cur.rounding
            ) or float_compare(
                line.amount_currency, amount, precision_rounding=company_cur.rounding
            ):
                line_cmds.append(
                    Command.update(
                        line.id,
                        {
                            "amount_currency": amount,
                            "balance": amount,
                        },
                    )
                )
        if not line_cmds:
            return
        self.with_context(
            skip_invoice_sync=True,
            check_move_validity=False,
        ).write({"line_ids": line_cmds})

    def _l10n_ve_refund_line_posted_company_subtotal(self, origin_line):
        self.ensure_one()
        origin = origin_line.move_id
        company_cur = origin.company_currency_id
        match_key = origin._l10n_ve_credit_note_line_match_key(origin_line)
        posted = 0.0
        for credit in origin._l10n_ve_posted_credit_notes_for_remaining():
            if credit == self:
                continue
            for line in credit.invoice_line_ids.filtered(
                lambda credit_line: credit_line.display_type == "product"
            ):
                if credit._l10n_ve_credit_note_line_match_key(line) == match_key:
                    posted += abs(line.balance)
        return company_cur.round(posted)

    def _l10n_ve_refund_line_posted_quantity(self, origin_line):
        self.ensure_one()
        origin = origin_line.move_id
        match_key = origin._l10n_ve_credit_note_line_match_key(origin_line)
        posted_qty = 0.0
        for credit in origin._l10n_ve_posted_credit_notes_for_remaining():
            if credit == self:
                continue
            for line in credit.invoice_line_ids.filtered(
                lambda credit_line: credit_line.display_type == "product"
            ):
                if credit._l10n_ve_credit_note_line_match_key(line) == match_key:
                    posted_qty += abs(line.quantity or 0.0)
        return posted_qty

    def _l10n_ve_refund_line_target_company_subtotal(self, origin_line, credit_line):
        company_cur = credit_line.company_currency_id
        origin_subtotal = self._l10n_ve_company_subtotal_from_origin_line(origin_line)
        if not origin_line.quantity:
            return company_cur.round(origin_subtotal)
        qty_ratio = credit_line.quantity / origin_line.quantity
        if self._l10n_ve_refund_line_uses_origin_company_amounts(
            origin_line, credit_line
        ):
            target = company_cur.round(origin_subtotal * qty_ratio)
        elif (
            credit_line.currency_id == origin_line.currency_id
            and credit_line.currency_id != company_cur
            and origin_line.price_unit
        ):
            price_ratio = credit_line.price_unit / origin_line.price_unit
            target = company_cur.round(origin_subtotal * qty_ratio * price_ratio)
        else:
            origin_pu = self._l10n_ve_company_price_unit_from_origin_line(origin_line)
            if not origin_pu or credit_line.currency_id != company_cur:
                target = company_cur.round(origin_subtotal * qty_ratio)
            else:
                target = company_cur.round(
                    origin_subtotal * qty_ratio * (credit_line.price_unit / origin_pu)
                )
        posted = self._l10n_ve_refund_line_posted_company_subtotal(origin_line)
        remaining = company_cur.round(origin_subtotal - posted)
        if company_cur.compare_amounts(remaining, 0.0) <= 0:
            return 0.0
        posted_qty = self._l10n_ve_refund_line_posted_quantity(origin_line)
        remaining_qty = abs(origin_line.quantity or 0.0) - posted_qty
        qty_prec = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        price_prec = self.env["decimal.precision"].precision_get("Product Price")
        completes_qty = not float_compare(
            abs(credit_line.quantity or 0.0),
            remaining_qty,
            precision_digits=qty_prec,
        )
        same_price = (
            credit_line.currency_id == origin_line.currency_id
            and not float_compare(
                credit_line.price_unit or 0.0,
                origin_line.price_unit or 0.0,
                precision_digits=price_prec,
            )
        )
        if completes_qty and same_price:
            return remaining
        if company_cur.compare_amounts(target, remaining) > 0:
            return remaining
        return target

    def _l10n_ve_refund_line_target_company_price_unit(self, origin_line, credit_line):
        origin_pu = self._l10n_ve_company_price_unit_from_origin_line(origin_line)
        if self._l10n_ve_refund_line_uses_origin_company_amounts(
            origin_line, credit_line
        ):
            return origin_pu
        if credit_line.currency_id == credit_line.company_currency_id:
            return credit_line.price_unit
        return self._l10n_ve_company_price_unit_from_refund_line(
            origin_line, credit_line
        )

    def _l10n_ve_align_refund_company_amounts_to_origin(self):
        for move in self:
            move._l10n_ve_align_refund_company_amounts_on_move()

    def _l10n_ve_align_refund_should_pair_origin(self):
        origin = self.reversed_entry_id
        if (
            self.move_type != "out_refund"
            or not origin
            or origin.currency_id == origin.company_currency_id
            or self.country_code != self.env.ref("base.ve").code
        ):
            return False
        if self.currency_id not in (self.company_currency_id, origin.currency_id):
            return False
        if (
            hasattr(self, "_l10n_ve_is_post_discount_credit_note")
            and self._l10n_ve_is_post_discount_credit_note()
        ):
            self._l10n_ve_cap_refund_company_amount_to_remaining()
            return False
        return True

    def _l10n_ve_align_refund_product_pairs(self):
        pairs = self._l10n_ve_refund_origin_credit_line_pairs(self.reversed_entry_id)
        if pairs is None:
            pairing_reason = _(
                "No se pudieron emparejar las lineas de producto con la "
                "factura origen."
            )
            self.message_post(body=pairing_reason)
            self._l10n_ve_cap_refund_company_amount_to_remaining()
            return None, None
        orig_products = self.env["account.move.line"]
        cred_products = self.env["account.move.line"]
        for origin_line, credit_line in pairs:
            if origin_line.display_type not in ("product", "cogs"):
                continue
            orig_products += origin_line
            cred_products += credit_line
        if not cred_products:
            self._l10n_ve_cap_refund_company_amount_to_remaining()
            return None, None
        return orig_products, cred_products

    def _l10n_ve_align_refund_write_product_price_units(
        self, orig_products, cred_products
    ):
        if self.currency_id != self.company_currency_id:
            return cred_products
        price_prec = self.env["decimal.precision"].precision_get("Product Price")
        same_currency = self.currency_id == self.reversed_entry_id.currency_id
        price_cmds = []
        for origin_line, credit_line in zip(orig_products, cred_products, strict=False):
            if same_currency:
                continue
            price_unit = self._l10n_ve_refund_line_target_company_price_unit(
                origin_line, credit_line
            )
            if float_compare(
                credit_line.price_unit, price_unit, precision_digits=price_prec
            ):
                price_cmds.append(
                    Command.update(credit_line.id, {"price_unit": price_unit})
                )
        if not price_cmds:
            return cred_products
        self.with_context(l10n_ve_skip_refund_realign=True).write(
            {"invoice_line_ids": price_cmds}
        )
        refreshed_ids = set(self.invoice_line_ids.ids)
        return self.env["account.move.line"].browse(
            [line.id for line in cred_products if line.id in refreshed_ids]
        )

    def _l10n_ve_align_refund_is_full_origin_mirror(
        self, orig_products, cred_products
    ):
        if len(orig_products) != len(cred_products):
            return False
        origin_products = self.reversed_entry_id.invoice_line_ids.filtered(
            lambda line: line.display_type in ("product", "cogs")
        )
        if len(origin_products) != len(orig_products):
            return False
        qty_prec = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        return all(
            not float_compare(
                abs(origin_line.quantity or 0.0),
                abs(credit_line.quantity or 0.0),
                precision_digits=qty_prec,
            )
            for origin_line, credit_line in zip(
                orig_products, cred_products, strict=False
            )
        )

    def _l10n_ve_align_refund_balance_cmd(
        self, credit_line, amount, amount_currency=None
    ):
        company_cur = self.company_currency_id
        vals = {}
        if float_compare(
            credit_line.balance, amount, precision_rounding=company_cur.rounding
        ):
            vals["balance"] = amount
        if amount_currency is None:
            if self.currency_id == company_cur:
                amount_currency = amount
            else:
                amount_currency = credit_line.amount_currency
        currency = self.currency_id
        if float_compare(
            credit_line.amount_currency,
            amount_currency,
            precision_rounding=currency.rounding,
        ):
            vals["amount_currency"] = amount_currency
        if not vals:
            return None
        return Command.update(credit_line.id, vals)

    def _l10n_ve_align_refund_product_balance_cmds(self, orig_products, cred_products):
        company_cur = self.company_currency_id
        same_currency = self.currency_id == self.reversed_entry_id.currency_id
        line_cmds = []
        for origin_line, credit_line in zip(orig_products, cred_products, strict=False):
            sign = 1.0 if credit_line.balance >= 0.0 else -1.0
            amount = (
                company_cur.round(
                    self._l10n_ve_refund_line_target_company_subtotal(
                        origin_line, credit_line
                    )
                )
                * sign
            )
            amount_currency = None
            if same_currency:
                qty_ratio = (
                    (credit_line.quantity / origin_line.quantity)
                    if origin_line.quantity
                    else 1.0
                )
                price_ratio = (
                    (credit_line.price_unit / origin_line.price_unit)
                    if origin_line.price_unit
                    else 1.0
                )
                target_currency = self.currency_id.round(
                    abs(origin_line.amount_currency)
                    * abs(qty_ratio)
                    * abs(price_ratio)
                )
                posted_currency = 0.0
                match_key = self.reversed_entry_id._l10n_ve_credit_note_line_match_key(
                    origin_line
                )
                for credit in self.reversed_entry_id._l10n_ve_posted_credit_notes_for_remaining():
                    if credit == self:
                        continue
                    for line in credit.invoice_line_ids.filtered(
                        lambda credit_line: credit_line.display_type == "product"
                    ):
                        if (
                            credit._l10n_ve_credit_note_line_match_key(line)
                            == match_key
                        ):
                            posted_currency += abs(line.amount_currency)
                remaining_currency = self.currency_id.round(
                    abs(origin_line.amount_currency) - posted_currency
                )
                posted_qty = self._l10n_ve_refund_line_posted_quantity(origin_line)
                remaining_qty = abs(origin_line.quantity or 0.0) - posted_qty
                qty_prec = self.env["decimal.precision"].precision_get(
                    "Product Unit of Measure"
                )
                price_prec = self.env["decimal.precision"].precision_get(
                    "Product Price"
                )
                same_price = not float_compare(
                    credit_line.price_unit or 0.0,
                    origin_line.price_unit or 0.0,
                    precision_digits=price_prec,
                )
                if (
                    not float_compare(
                        abs(credit_line.quantity or 0.0),
                        remaining_qty,
                        precision_digits=qty_prec,
                    )
                    and same_price
                ):
                    target_currency = remaining_currency
                elif self.currency_id.compare_amounts(
                    target_currency, remaining_currency
                ) > 0:
                    target_currency = remaining_currency
                amount_currency = target_currency * (
                    1.0 if credit_line.amount_currency >= 0.0 else -1.0
                )
            command = self._l10n_ve_align_refund_balance_cmd(
                credit_line, amount, amount_currency=amount_currency
            )
            if command:
                line_cmds.append(command)
        return line_cmds

    def _l10n_ve_align_refund_discount_balance_cmds(self):
        company_cur = self.company_currency_id
        same_currency = self.currency_id == self.reversed_entry_id.currency_id
        line_cmds = []
        origin = self.reversed_entry_id
        for discount_type in ("rounding", "discount", "global_discount"):
            orig_discounts = origin.line_ids.filtered(
                lambda line, discount_type=discount_type: (
                    line.display_type == discount_type
                )
            ).sorted(lambda line: (line.sequence, line.id))
            cred_discounts = self.line_ids.filtered(
                lambda line, discount_type=discount_type: (
                    line.display_type == discount_type
                )
            ).sorted(lambda line: (line.sequence, line.id))
            if orig_discounts and len(orig_discounts) == len(cred_discounts):
                for origin_line, credit_line in zip(
                    orig_discounts, cred_discounts, strict=False
                ):
                    sign = 1.0 if credit_line.balance >= 0.0 else -1.0
                    amount = (
                        company_cur.round(
                            self._l10n_ve_company_subtotal_from_origin_line(origin_line)
                        )
                        * sign
                    )
                    amount_currency = None
                    if same_currency:
                        amount_currency = self.currency_id.round(
                            abs(origin_line.amount_currency)
                        ) * (1.0 if credit_line.amount_currency >= 0.0 else -1.0)
                    command = self._l10n_ve_align_refund_balance_cmd(
                        credit_line, amount, amount_currency=amount_currency
                    )
                    if command:
                        line_cmds.append(command)
            elif cred_discounts and not orig_discounts:
                for credit_line in cred_discounts:
                    if not company_cur.is_zero(
                        credit_line.balance
                    ) or not self.currency_id.is_zero(credit_line.amount_currency):
                        line_cmds.append(
                            Command.update(
                                credit_line.id,
                                {"amount_currency": 0.0, "balance": 0.0},
                            )
                        )
        return line_cmds

    def _l10n_ve_align_refund_company_amounts_on_move(self):
        self.ensure_one()
        if not self._l10n_ve_align_refund_should_pair_origin():
            return
        orig_products, cred_products = self._l10n_ve_align_refund_product_pairs()
        if orig_products is None:
            return
        cred_products = self._l10n_ve_align_refund_write_product_price_units(
            orig_products, cred_products
        )
        line_cmds = self._l10n_ve_align_refund_product_balance_cmds(
            orig_products, cred_products
        )
        line_cmds.extend(self._l10n_ve_align_refund_discount_balance_cmds())
        if line_cmds:
            self.with_context(
                skip_invoice_sync=True,
                check_move_validity=False,
            ).write({"line_ids": line_cmds})
            self._l10n_ve_resync_refund_payment_term_after_tax_align()
        if self._l10n_ve_align_refund_is_full_origin_mirror(
            orig_products, cred_products
        ):
            self._l10n_ve_copy_origin_tax_company_amounts_on_move()
        else:
            self._l10n_ve_cap_refund_company_amount_to_remaining()

    @api.depends(
        "invoice_line_ids.currency_rate",
        "invoice_line_ids.tax_base_amount",
        "invoice_line_ids.tax_line_id",
        "invoice_line_ids.price_total",
        "invoice_line_ids.price_subtotal",
        "invoice_payment_term_id",
        "partner_id",
        "currency_id",
        "invoice_line_ids.product_id",
        "line_ids.balance",
        "line_ids.amount_currency",
        "amount_untaxed",
        "amount_tax",
        "amount_total",
        "reversed_entry_id",
    )
    def _compute_tax_totals(self):
        super()._compute_tax_totals()
        for move in self:
            if not move.tax_totals:
                continue
            move.tax_totals = move._l10n_ve_align_refund_tax_totals_to_accounting(
                move.tax_totals
            )

    def write(self, vals):
        realign_moves = self.env["account.move"]
        if (
            not self.env.context.get("l10n_ve_skip_refund_realign")
            and "invoice_line_ids" in vals
        ):
            realign_moves = self.filtered(
                lambda move: move.state == "draft"
                and move._l10n_ve_refund_tax_totals_should_follow_accounting()
            )
        res = super().write(vals)
        if realign_moves:
            realign_moves.with_context(
                l10n_ve_skip_refund_realign=True
            )._l10n_ve_realign_refund_on_draft_line_change()
        return res

    def _l10n_ve_realign_refund_on_draft_line_change(self):
        for move in self:
            if not move._l10n_ve_refund_tax_totals_should_follow_accounting():
                continue
            container = {"records": move}
            with move._sync_dynamic_lines(container):
                pass
            move._l10n_ve_align_refund_company_amounts_to_origin()

    def _l10n_ve_refund_is_full_origin_line_mirror(self):
        self.ensure_one()
        origin = self.reversed_entry_id
        if not origin:
            return False
        origin_products = origin.invoice_line_ids.filtered(
            lambda line: line.display_type in ("product", "cogs")
        )
        credit_products = self.invoice_line_ids.filtered(
            lambda line: line.display_type in ("product", "cogs")
        )
        if len(origin_products) != len(credit_products):
            return False
        qty_prec = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        origin_by_key = {}
        for line in origin_products:
            key = origin._l10n_ve_credit_note_line_match_key(line)
            origin_by_key.setdefault(key, []).append(line)
        for credit_line in credit_products:
            key = self._l10n_ve_credit_note_line_match_key(credit_line)
            candidates = origin_by_key.get(key)
            if not candidates:
                return False
            origin_line = candidates.pop(0)
            if float_compare(
                abs(credit_line.quantity or 0.0),
                abs(origin_line.quantity or 0.0),
                precision_digits=qty_prec,
            ):
                return False
        return True

    def _l10n_ve_refund_tax_totals_should_follow_accounting(self):
        self.ensure_one()
        origin = self.reversed_entry_id
        if (
            self.move_type != "out_refund"
            or not origin
            or origin.currency_id == origin.company_currency_id
            or self.country_code != self.env.ref("base.ve").code
        ):
            return False
        if self.currency_id not in (self.company_currency_id, origin.currency_id):
            return False
        if (
            hasattr(self, "_l10n_ve_is_post_discount_credit_note")
            and self._l10n_ve_is_post_discount_credit_note()
        ):
            return False
        return True

    def _l10n_ve_align_refund_tax_totals_to_accounting(self, tax_totals):
        self.ensure_one()
        if not tax_totals or not (
            self._l10n_ve_refund_tax_totals_should_follow_accounting()
        ):
            return tax_totals
        origin = self.reversed_entry_id
        company_cur = self.company_currency_id
        totals = deepcopy(tax_totals)
        base_company = company_cur.round(abs(self.amount_untaxed_signed))
        tax_company = company_cur.round(abs(self.amount_tax_signed))
        total_company = company_cur.round(abs(self.amount_total_signed))
        if self.currency_id == origin.currency_id:
            base_currency = self.currency_id.round(abs(self.amount_untaxed))
            tax_currency = self.currency_id.round(abs(self.amount_tax))
            total_currency = self.currency_id.round(abs(self.amount_total))
        else:
            base_currency = base_company
            tax_currency = tax_company
            total_currency = total_company
        totals["base_amount_currency"] = base_currency
        totals["base_amount"] = base_company
        totals["tax_amount_currency"] = tax_currency
        totals["tax_amount"] = tax_company
        totals["total_amount_currency"] = total_currency
        totals["total_amount"] = total_company
        self._l10n_ve_scale_refund_tax_subtotals(
            totals,
            base_currency,
            base_company,
            tax_currency,
            tax_company,
        )
        self._l10n_ve_align_refund_tax_totals_discount_fields(totals, base_company)
        return totals

    def _l10n_ve_scale_refund_tax_subtotals(
        self, totals, base_currency, base_company, tax_currency, tax_company
    ):
        company_cur = self.company_currency_id
        currency = self.currency_id
        subtotals = totals.get("subtotals") or []
        if not subtotals:
            return
        sum_base_currency = sum(
            subtotal.get("base_amount_currency", 0.0) for subtotal in subtotals
        )
        sum_base_company = sum(
            subtotal.get("base_amount", 0.0) for subtotal in subtotals
        )
        sum_tax_currency = sum(
            subtotal.get("tax_amount_currency", 0.0) for subtotal in subtotals
        )
        sum_tax_company = sum(
            subtotal.get("tax_amount", 0.0) for subtotal in subtotals
        )
        allocated_base_currency = 0.0
        allocated_base_company = 0.0
        allocated_tax_currency = 0.0
        allocated_tax_company = 0.0
        last_index = len(subtotals) - 1
        for index, subtotal in enumerate(subtotals):
            if len(subtotals) == 1:
                subtotal["base_amount_currency"] = base_currency
                subtotal["base_amount"] = base_company
                subtotal["tax_amount_currency"] = tax_currency
                subtotal["tax_amount"] = tax_company
            elif index == last_index:
                subtotal["base_amount_currency"] = currency.round(
                    base_currency - allocated_base_currency
                )
                subtotal["base_amount"] = company_cur.round(
                    base_company - allocated_base_company
                )
                subtotal["tax_amount_currency"] = currency.round(
                    tax_currency - allocated_tax_currency
                )
                subtotal["tax_amount"] = company_cur.round(
                    tax_company - allocated_tax_company
                )
            else:
                if not float_is_zero(
                    sum_base_currency, precision_rounding=currency.rounding
                ):
                    ratio = (
                        subtotal.get("base_amount_currency", 0.0) / sum_base_currency
                    )
                    subtotal["base_amount_currency"] = currency.round(
                        base_currency * ratio
                    )
                if not float_is_zero(
                    sum_base_company, precision_rounding=company_cur.rounding
                ):
                    ratio = subtotal.get("base_amount", 0.0) / sum_base_company
                    subtotal["base_amount"] = company_cur.round(
                        base_company * ratio
                    )
                if not float_is_zero(
                    sum_tax_currency, precision_rounding=currency.rounding
                ):
                    ratio = (
                        subtotal.get("tax_amount_currency", 0.0) / sum_tax_currency
                    )
                    subtotal["tax_amount_currency"] = currency.round(
                        tax_currency * ratio
                    )
                if not float_is_zero(
                    sum_tax_company, precision_rounding=company_cur.rounding
                ):
                    ratio = subtotal.get("tax_amount", 0.0) / sum_tax_company
                    subtotal["tax_amount"] = company_cur.round(tax_company * ratio)
                allocated_base_currency += subtotal.get("base_amount_currency", 0.0)
                allocated_base_company += subtotal.get("base_amount", 0.0)
                allocated_tax_currency += subtotal.get("tax_amount_currency", 0.0)
                allocated_tax_company += subtotal.get("tax_amount", 0.0)
            groups = subtotal.get("tax_groups") or []
            group_tax_currency = sum(
                group.get("tax_amount_currency", 0.0) for group in groups
            )
            group_tax_company = sum(
                group.get("tax_amount", 0.0) for group in groups
            )
            for group in groups:
                if len(groups) == 1:
                    group["base_amount_currency"] = subtotal["base_amount_currency"]
                    group["base_amount"] = subtotal["base_amount"]
                    group["display_base_amount_currency"] = subtotal[
                        "base_amount_currency"
                    ]
                    group["display_base_amount"] = subtotal["base_amount"]
                    group["tax_amount_currency"] = subtotal["tax_amount_currency"]
                    group["tax_amount"] = subtotal["tax_amount"]
                else:
                    if not float_is_zero(
                        group_tax_currency, precision_rounding=currency.rounding
                    ):
                        ratio = (
                            group.get("tax_amount_currency", 0.0) / group_tax_currency
                        )
                        group["tax_amount_currency"] = currency.round(
                            subtotal["tax_amount_currency"] * ratio
                        )
                    if not float_is_zero(
                        group_tax_company, precision_rounding=company_cur.rounding
                    ):
                        ratio = group.get("tax_amount", 0.0) / group_tax_company
                        group["tax_amount"] = company_cur.round(
                            subtotal["tax_amount"] * ratio
                        )
                    group["display_base_amount_currency"] = group.get(
                        "base_amount_currency", 0.0
                    )
                    group["display_base_amount"] = group.get("base_amount", 0.0)

    def _l10n_ve_align_refund_tax_totals_discount_fields(self, totals, base):
        origin = self.reversed_entry_id
        origin_totals = origin.tax_totals or {}
        same_currency = self.currency_id == origin.currency_id
        full_mirror = self._l10n_ve_refund_is_full_origin_line_mirror()
        origin_discount_company = origin_totals.get("l10n_ve_global_discount_amount")
        origin_gross_company = origin_totals.get("l10n_ve_subtotal_gross")
        origin_discount_currency = origin_totals.get(
            "l10n_ve_global_discount_amount_currency"
        )
        origin_gross_currency = origin_totals.get("l10n_ve_subtotal_gross_currency")
        if (
            full_mirror
            and origin_discount_company
            and origin_gross_company
        ):
            discount_company = self.company_currency_id.round(origin_discount_company)
            gross_company = self.company_currency_id.round(origin_gross_company)
        else:
            gross_company = totals.get("l10n_ve_subtotal_gross") or 0.0
            discount_company = self.company_currency_id.round(gross_company - base)
        if (
            full_mirror
            and same_currency
            and origin_discount_currency
            and origin_gross_currency
        ):
            discount_currency = self.currency_id.round(origin_discount_currency)
            gross_currency = self.currency_id.round(origin_gross_currency)
        elif same_currency:
            gross_currency = totals.get("l10n_ve_subtotal_gross_currency") or 0.0
            discount_currency = self.currency_id.round(
                gross_currency - abs(self.amount_untaxed)
            )
        else:
            discount_currency = discount_company
            gross_currency = gross_company
        totals["l10n_ve_subtotal_gross"] = gross_company
        totals["l10n_ve_subtotal_gross_currency"] = gross_currency
        totals["l10n_ve_global_discount_amount"] = discount_company
        totals["l10n_ve_global_discount_amount_currency"] = discount_currency
        lines = list(totals.get("l10n_ve_global_discount_lines") or [])
        if len(lines) == 1:
            line = dict(lines[0])
            line["amount"] = discount_currency if same_currency else discount_company
            totals["l10n_ve_global_discount_lines"] = [line]

    def _l10n_ve_cap_refund_company_amount_to_remaining(self, reason=None):
        self.ensure_one()
        origin = self.reversed_entry_id
        if not origin:
            return
        if self.currency_id not in (self.company_currency_id, origin.currency_id):
            return
        company_cur = self.company_currency_id
        remaining = company_cur.round(
            origin._l10n_ve_max_credit_note_company_amount()
            - origin._l10n_ve_posted_credit_notes_company_amount()
        )
        current = company_cur.round(self._l10n_ve_to_company_abs_amount())
        if (
            float_compare(current, remaining, precision_rounding=company_cur.rounding)
            <= 0
        ):
            return
        excess = company_cur.round(current - remaining)
        product_lines = self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        ).sorted(lambda line: (line.sequence, line.id))
        if not product_lines:
            return
        self._l10n_ve_cap_refund_apply_excess(product_lines, excess, reason=reason)

    def _l10n_ve_cap_refund_apply_excess(self, product_lines, excess, reason=None):
        company_cur = self.company_currency_id
        currency = self.currency_id
        same_company_currency = currency == company_cur
        price_prec = self.env["decimal.precision"].precision_get("Product Price")
        leftover = excess
        unlink_lines = self.env["account.move.line"]
        line_cmds = []
        for line in reversed(product_lines):
            if (
                float_compare(leftover, 0.0, precision_rounding=company_cur.rounding)
                <= 0
            ):
                break
            line_abs = abs(line.balance)
            if company_cur.is_zero(line_abs):
                continue
            take = min(line_abs, leftover)
            leftover = company_cur.round(leftover - take)
            new_abs = company_cur.round(line_abs - take)
            if company_cur.is_zero(new_abs):
                unlink_lines |= line
                continue
            ratio = new_abs / line_abs
            discount_factor = 1.0 - (line.discount or 0.0) / 100.0
            quantity = abs(line.quantity) or 1.0
            if discount_factor <= 0.0:
                unlink_lines |= line
                leftover = company_cur.round(leftover + new_abs)
                continue
            if same_company_currency:
                price_unit = new_abs / quantity / discount_factor
                amount_currency = company_cur.round(new_abs)
            else:
                new_amount_currency = currency.round(
                    abs(line.amount_currency) * ratio
                )
                price_unit = new_amount_currency / quantity / discount_factor
                amount_currency = new_amount_currency
            if float_compare(price_unit, 0.0, precision_digits=price_prec) <= 0:
                unlink_lines |= line
                leftover = company_cur.round(leftover + new_abs)
                continue
            balance_sign = 1.0 if line.balance >= 0.0 else -1.0
            amount_sign = 1.0 if line.amount_currency >= 0.0 else -1.0
            line_cmds.append(
                Command.update(
                    line.id,
                    {
                        "price_unit": price_unit,
                        "amount_currency": amount_currency * amount_sign,
                        "balance": company_cur.round(new_abs) * balance_sign,
                    },
                )
            )
        if unlink_lines:
            unlink_lines.with_context(dynamic_unlink=True).unlink()
        if line_cmds:
            self.with_context(
                skip_invoice_sync=True,
                check_move_validity=False,
            ).write({"line_ids": line_cmds})
        if unlink_lines or line_cmds:
            self._l10n_ve_resync_refund_payment_term_after_tax_align()
            body_parts = []
            if reason:
                body_parts.append(reason)
            body_parts.append(
                _(
                    "Se ajustaron lineas de la nota de credito al saldo "
                    "restante permitido de la factura origen."
                )
            )
            self.message_post(body=" ".join(body_parts))


    def _l10n_ve_to_company_abs_amount(self):
        self.ensure_one()
        amount = super()._l10n_ve_to_company_abs_amount()
        if (
            self.move_type != "out_refund"
            or not self.reversed_entry_id
            or self.currency_id == self.company_currency_id
            or self.country_code != self.env.ref("base.ve").code
        ):
            return amount
        origin = self.reversed_entry_id
        company_cur = self.company_currency_id
        origin_total = abs(origin.amount_total)
        origin_company = origin._l10n_ve_to_company_abs_amount()
        if (
            self.currency_id == origin.currency_id
            and not self.currency_id.is_zero(origin_total)
            and not company_cur.is_zero(origin_company)
        ):
            ratio = abs(self.amount_total) / origin_total
            return company_cur.round(origin_company * ratio)
        origin_date = (
            origin.invoice_date or origin.date or fields.Date.context_today(self)
        )
        return company_cur.round(
            self.currency_id._convert(
                abs(self.amount_total),
                company_cur,
                self.company_id,
                origin_date,
            )
        )

    def action_post(self):
        ve_code = self.env.ref("base.ve").code
        refunds = self.filtered(
            lambda move: move.country_code == ve_code
            and move.move_type == "out_refund"
            and move.state == "draft"
            and move.reversed_entry_id
            and move.reversed_entry_id.currency_id
            != move.reversed_entry_id.company_currency_id
        )
        if refunds:
            refunds._l10n_ve_lock_refund_invoice_currency_rate_from_origin()
            refunds._l10n_ve_align_refund_company_amounts_to_origin()
        return super().action_post()

