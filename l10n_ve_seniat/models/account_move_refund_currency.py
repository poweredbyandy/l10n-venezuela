from collections import defaultdict

from odoo import _, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tools import float_compare, float_round


# pylint: disable=consider-merging-classes-inherited
class AccountMove(models.Model):
    _inherit = "account.move"

    def _l10n_ve_requires_refund_company_currency(self):
        self.ensure_one()
        if "l10n_ve_emission_medium" not in self.journal_id._fields:
            return False
        return bool(self.journal_id.l10n_ve_emission_medium)

    def _l10n_ve_company_price_unit_from_origin_line(self, line):
        if line.currency_id == line.company_currency_id:
            return line.price_unit
        qty = abs(line.quantity or 0.0)
        if not qty:
            return line.price_unit_company_currency
        discount_factor = 1.0 - (line.discount or 0.0) / 100.0
        if discount_factor <= 0.0:
            return 0.0
        subtotal = self._l10n_ve_company_subtotal_from_origin_line(line)
        prec = self.env["decimal.precision"].precision_get("Product Price")
        return float_round(subtotal / discount_factor / qty, precision_digits=prec)

    def _l10n_ve_company_subtotal_from_origin_line(self, line):
        if line.currency_id == line.company_currency_id:
            return abs(line.price_subtotal)
        return line.price_subtotal_currency

    def _l10n_ve_refund_line_uses_origin_company_amounts(
        self, origin_line, credit_line
    ):
        company_cur = credit_line.company_currency_id
        origin_pu = self._l10n_ve_company_price_unit_from_origin_line(origin_line)
        price_prec = self.env["decimal.precision"].precision_get("Product Price")
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

    def _l10n_ve_force_refund_to_company_currency(self):
        ve_country = self.env.ref("base.ve").code
        for move in self:
            if (
                move.country_code != ve_country
                or move.move_type != "out_refund"
                or move.currency_id == move.company_currency_id
                or not move._l10n_ve_requires_refund_company_currency()
            ):
                continue
            origin = move.reversed_entry_id
            if not origin or origin.currency_id == origin.company_currency_id:
                continue
            if (
                hasattr(move, "_l10n_ve_is_post_discount_credit_note")
                and move._l10n_ve_is_post_discount_credit_note()
            ):
                move._l10n_ve_apply_company_currency_from_line_balances()
                continue
            pairs = move._l10n_ve_refund_origin_credit_line_pairs(origin)
            if pairs is None:
                raise ValidationError(
                    _(
                        "La nota de crédito '%(credit)s' no coincide en líneas "
                        "con la factura origen '%(origin)s'. Revise el borrador "
                        "o cree la reversión desde el asistente estándar."
                    )
                    % {
                        "credit": move.display_name,
                        "origin": origin.display_name,
                    }
                )
            line_cmds = []
            for origin_line, credit_line in pairs:
                if origin_line.display_type != credit_line.display_type:
                    raise ValidationError(
                        _(
                            "Las líneas de la nota de crédito no coinciden con "
                            "la factura origen (tipo de línea distinto)."
                        )
                    )
                command = move._l10n_ve_refund_convert_paired_line_cmd(
                    origin_line, credit_line
                )
                if command:
                    line_cmds.append(command)
            vals = {"currency_id": move.company_currency_id.id}
            if line_cmds:
                vals["invoice_line_ids"] = line_cmds
            move.write(vals)
            move.flush_recordset()
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
        return self

    def _l10n_ve_copy_origin_tax_company_amounts_on_move(self):
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

    def _l10n_ve_refund_line_target_company_subtotal(self, origin_line, credit_line):
        company_cur = credit_line.company_currency_id
        origin_subtotal = self._l10n_ve_company_subtotal_from_origin_line(origin_line)
        if not origin_line.quantity:
            return company_cur.round(origin_subtotal)
        qty_ratio = credit_line.quantity / origin_line.quantity
        if self._l10n_ve_refund_line_uses_origin_company_amounts(
            origin_line, credit_line
        ):
            return company_cur.round(origin_subtotal * qty_ratio)
        origin_pu = self._l10n_ve_company_price_unit_from_origin_line(origin_line)
        if not origin_pu or credit_line.currency_id != company_cur:
            return company_cur.round(origin_subtotal * qty_ratio)
        return company_cur.round(
            origin_subtotal * qty_ratio * (credit_line.price_unit / origin_pu)
        )

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
            or self.currency_id != self.company_currency_id
            or origin.currency_id == origin.company_currency_id
            or self.country_code != self.env.ref("base.ve").code
        ):
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
        price_prec = self.env["decimal.precision"].precision_get("Product Price")
        price_cmds = []
        for origin_line, credit_line in zip(orig_products, cred_products, strict=False):
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
        self.write({"invoice_line_ids": price_cmds})
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type in ("product", "cogs")
        ).sorted(lambda line: (line.sequence, line.id))

    def _l10n_ve_align_refund_balance_cmd(self, credit_line, amount):
        company_cur = self.company_currency_id
        if float_compare(
            credit_line.balance, amount, precision_rounding=company_cur.rounding
        ) or float_compare(
            credit_line.amount_currency,
            amount,
            precision_rounding=company_cur.rounding,
        ):
            return Command.update(
                credit_line.id,
                {"amount_currency": amount, "balance": amount},
            )
        return None

    def _l10n_ve_align_refund_product_balance_cmds(self, orig_products, cred_products):
        company_cur = self.company_currency_id
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
            command = self._l10n_ve_align_refund_balance_cmd(credit_line, amount)
            if command:
                line_cmds.append(command)
        return line_cmds

    def _l10n_ve_align_refund_discount_balance_cmds(self):
        company_cur = self.company_currency_id
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
                    command = self._l10n_ve_align_refund_balance_cmd(
                        credit_line, amount
                    )
                    if command:
                        line_cmds.append(command)
            elif cred_discounts and not orig_discounts:
                for credit_line in cred_discounts:
                    if not company_cur.is_zero(
                        credit_line.balance
                    ) or not company_cur.is_zero(credit_line.amount_currency):
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
        self._l10n_ve_cap_refund_company_amount_to_remaining()

    def _l10n_ve_cap_refund_company_amount_to_remaining(self):
        self.ensure_one()
        origin = self.reversed_entry_id
        if not origin or self.currency_id != self.company_currency_id:
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
        self._l10n_ve_cap_refund_apply_excess(product_lines, excess)

    def _l10n_ve_cap_refund_apply_excess(self, product_lines, excess):
        company_cur = self.company_currency_id
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
            take = min(line_abs, leftover)
            leftover = company_cur.round(leftover - take)
            new_abs = company_cur.round(line_abs - take)
            if company_cur.is_zero(new_abs):
                unlink_lines |= line
                continue
            discount_factor = 1.0 - (line.discount or 0.0) / 100.0
            quantity = abs(line.quantity) or 1.0
            if discount_factor <= 0.0:
                unlink_lines |= line
                leftover = company_cur.round(leftover + new_abs)
                continue
            price_unit = new_abs / quantity / discount_factor
            if float_compare(price_unit, 0.0, precision_digits=price_prec) <= 0:
                unlink_lines |= line
                leftover = company_cur.round(leftover + new_abs)
                continue
            sign = 1.0 if line.balance >= 0.0 else -1.0
            line_cmds.append(
                Command.update(
                    line.id,
                    {
                        "price_unit": price_unit,
                        "amount_currency": company_cur.round(new_abs) * sign,
                        "balance": company_cur.round(new_abs) * sign,
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
        to_company_refund = self.filtered(
            lambda m: m.country_code == ve_code
            and m.move_type == "out_refund"
            and m.state == "draft"
            and m.reversed_entry_id
            and m.currency_id != m.company_currency_id
            and m.reversed_entry_id.currency_id
            != m.reversed_entry_id.company_currency_id
            and m._l10n_ve_requires_refund_company_currency()
        )
        if to_company_refund:
            to_company_refund._l10n_ve_force_refund_to_company_currency()
        already_converted = self.filtered(
            lambda move: move.country_code == ve_code
            and move.move_type == "out_refund"
            and move.state == "draft"
            and move.reversed_entry_id
            and move.currency_id == move.company_currency_id
            and move.reversed_entry_id.currency_id
            != move.reversed_entry_id.company_currency_id
        )
        already_converted._l10n_ve_align_refund_company_amounts_to_origin()
        for move in self:
            if (
                move.country_code == ve_code
                and move.move_type == "out_refund"
                and move.currency_id != move.company_currency_id
                and move._l10n_ve_requires_refund_company_currency()
            ):
                raise ValidationError(
                    _(
                        "No se puede confirmar la nota de crédito '%(move)s'. "
                        "Las notas de crédito deben registrarse en bolívares "
                        "(moneda de la compañía)."
                    )
                    % {"move": move.name or _("Borrador")}
                )
        return super().action_post()
