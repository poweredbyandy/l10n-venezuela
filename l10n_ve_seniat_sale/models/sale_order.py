# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import Command, _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_is_zero


class SaleOrder(models.Model):
    _inherit = "sale.order"

    invoicing_date = fields.Date(
        string="Fecha de Facturación",
        compute="_compute_invoicing_date",
        store=True,
        readonly=False,
        help="Fecha en que se espera facturar. Se calcula según los términos de pago o puede establecerse manualmente.",
    )

    @api.depends("date_order", "payment_term_id", "commitment_date")
    def _compute_invoicing_date(self):
        for order in self:
            date_ref = order.commitment_date or order.date_order
            date_ref = date_ref.date() if date_ref and hasattr(date_ref, "date") else date_ref
            if date_ref and order.payment_term_id:
                amount = order.amount_untaxed or 1.0
                terms = order.payment_term_id._compute_terms(
                    date_ref=date_ref,
                    currency=order.currency_id or order.company_id.currency_id,
                    company=order.company_id,
                    tax_amount=0,
                    tax_amount_currency=0,
                    untaxed_amount=amount,
                    untaxed_amount_currency=amount,
                    sign=1,
                )
                if terms.get("line_ids"):
                    order.invoicing_date = max(line["date"] for line in terms["line_ids"])
                else:
                    order.invoicing_date = date_ref
            elif date_ref:
                order.invoicing_date = date_ref
            else:
                order.invoicing_date = False

    @api.depends("company_id")
    def _compute_journal_id(self):
        non_ve = self.filtered(lambda o: o.country_code != "VE")
        super(SaleOrder, non_ve)._compute_journal_id()
        for order in self - non_ve:
            if not order.journal_id:
                order.journal_id = order._l10n_ve_default_sale_journal()

    def _l10n_ve_default_sale_journal(self):
        self.ensure_one()
        return self.env["account.journal"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("type", "=", "sale"),
            ],
            order="sequence asc, id asc",
            limit=1,
        )

    def _l10n_ve_get_max_invoice_lines_from_book(self):
        self.ensure_one()
        book = self.journal_id.l10n_ve_invoice_section_id.book_id
        if not book:
            return 0
        return max(book.l10n_ve_max_invoice_lines or 10, 1)

    def _l10n_ve_product_line_count_invoiceable(self, invoiceable_lines):
        return len(
            invoiceable_lines.filtered(
                lambda line: not line.display_type and not line.is_downpayment
            )
        )

    def _l10n_ve_split_invoiceable_lines(self, invoiceable_lines, max_lines):
        self.ensure_one()
        lines = invoiceable_lines.sorted(key=lambda line: (line.sequence, line.id))
        chunks = []
        buf_ids = []
        prod_in_buf = 0
        pending_header_ids = []
        down_ids = []
        for line in lines:
            if line.is_downpayment:
                down_ids.append(line.id)
                continue
            if line.display_type in ("line_section", "line_note"):
                pending_header_ids.append(line.id)
                continue
            if prod_in_buf >= max_lines and buf_ids:
                chunks.append(buf_ids)
                buf_ids = []
                prod_in_buf = 0
            if pending_header_ids:
                buf_ids.extend(pending_header_ids)
                pending_header_ids = []
            buf_ids.append(line.id)
            prod_in_buf += 1
        if pending_header_ids:
            buf_ids.extend(pending_header_ids)
        if buf_ids:
            chunks.append(buf_ids)
        if down_ids:
            if chunks:
                chunks[-1].extend(down_ids)
            else:
                chunks.append(down_ids)
        return [invoiceable_lines.browse(ids) for ids in chunks]

    def _l10n_ve_invoiceable_line_chunks(self, final):
        self.ensure_one()
        invoiceable_lines = super()._get_invoiceable_lines(final)
        max_lines = self._l10n_ve_get_max_invoice_lines_from_book()
        if (
            max_lines <= 0
            or self._l10n_ve_product_line_count_invoiceable(invoiceable_lines) <= max_lines
        ):
            return [invoiceable_lines]
        return self._l10n_ve_split_invoiceable_lines(invoiceable_lines, max_lines)

    def _get_invoiceable_lines(self, final=False):
        lines = super()._get_invoiceable_lines(final)
        ids_ctx = self.env.context.get("l10n_ve_invoiceable_line_ids")
        if ids_ctx is not None:
            id_set = set(ids_ctx)
            lines = lines.filtered(lambda line: line.id in id_set)
        return lines

    def _create_invoices(self, grouped=False, final=False, date=None):
        if not self.env["account.move"].has_access("create"):
            try:
                self.check_access("write")
            except AccessError:
                return self.env["account.move"]
        ve = self.filtered(lambda o: o.country_code == "VE")
        non_ve = self - ve
        moves = (
            non_ve._create_invoices(grouped=grouped, final=final, date=date)
            if non_ve
            else self.env["account.move"]
        )
        for order in ve:
            chunks = order._l10n_ve_invoiceable_line_chunks(final)
            if len(chunks) <= 1:
                moves |= super(SaleOrder, order)._create_invoices(
                    grouped=False, final=final, date=date
                )
            else:
                for chunk in chunks:
                    moves |= super(
                        SaleOrder,
                        order.with_context(
                            l10n_ve_invoiceable_line_ids=tuple(chunk.ids)
                        ),
                    )._create_invoices(grouped=False, final=final, date=date)
        return moves

    def _l10n_ve_check_free_emission_correlatives(self):
        self.ensure_one()
        journal = self.journal_id
        if not journal:
            return
        if journal.l10n_ve_emission_medium != "free":
            return
        if not journal.l10n_ve_invoice_section_id:
            raise UserError(
                _(
                    "No se puede confirmar el pedido: el diario de ventas «%(journal)s» "
                    "está en «forma libre» (correlativo de talonario) y debe tener "
                    "configurado el tramo SENIAT de facturas de cliente."
                )
                % {"journal": journal.display_name}
            )
        if "warehouse_id" not in self._fields:
            return
        if "stock.warehouse" not in self.env:
            return
        Warehouse = self.env["stock.warehouse"]
        if "l10n_ve_dispatch_guide_section_id" not in Warehouse._fields:
            return
        warehouse = self.warehouse_id
        if not warehouse:
            raise UserError(
                _(
                    "No se puede confirmar el pedido: indique el almacén para validar "
                    "el correlativo de guía de despacho (SENIAT)."
                )
            )
        if not warehouse.l10n_ve_dispatch_guide_section_id:
            raise UserError(
                _(
                    "No se puede confirmar el pedido: con diario en «forma libre» debe "
                    "configurar en el almacén «%(warehouse)s» el tramo del talonario "
                    "para guías de despacho (SENIAT)."
                )
                % {"warehouse": warehouse.display_name}
            )

    def action_confirm(self):
        precision = self.env["decimal.precision"].precision_get("Product Price")
        for order in self:
            if float_is_zero(order.amount_total, precision_digits=order.currency_id.decimal_places):
                raise UserError(
                    "No se puede confirmar el pedido con un total de 0. "
                    "Agregue productos con precio o corrija los importes."
                )
            invalid_lines = order.order_line.filtered(
                lambda line: not line.display_type and float_is_zero(line.price_unit, precision_digits=precision)
            )
            if invalid_lines:
                products = [
                    line.product_id.display_name if line.product_id else line.name
                    for line in invalid_lines
                ]
                raise UserError(
                    "No se puede confirmar el pedido con líneas en precio 0. "
                    "Corrija los precios de los siguientes productos: %s"
                    % ", ".join(products)
                )
            if order.country_code == "VE":
                if not order.journal_id:
                    raise UserError(
                        _("Debe indicar el diario de ventas antes de confirmar el pedido.")
                    )
                order._l10n_ve_check_free_emission_correlatives()
                default_tax = order.company_id.account_sale_tax_id
                for line in order.order_line.filtered(lambda line: not line.display_type):
                    if len(line.tax_id) == 0:
                        if default_tax:
                            line.tax_id = [Command.link(default_tax.id)]
                            order.message_post(
                                body=_("Se agregó el impuesto por defecto a la línea: %s.")
                                % (line.name or _("Sin nombre"))
                            )
                        else:
                            raise UserError(
                                _(
                                    "La línea '%s' no tiene impuesto asignado. "
                                    "Asigne un impuesto o configure el impuesto de venta por defecto en la compañía."
                                )
                                % (line.name or _("Sin nombre"))
                            )
                lines_with_multi_tax = []
                for line in order.order_line.filtered(lambda line: not line.display_type):
                    if len(line.tax_id) > 1:
                        tax_mapped = ", ".join(line.tax_id.mapped("name"))
                        lines_with_multi_tax.append(" - %s: %s" % (line.name or _("Sin nombre"), tax_mapped))
                if lines_with_multi_tax:
                    raise UserError(
                        _(
                            "No se puede asignar más de un impuesto a una sola línea de pedido. "
                            "Cree líneas separadas para cada impuesto.\n%s"
                        )
                        % "\n".join(lines_with_multi_tax)
                    )
        return super().action_confirm()

    @api.depends_context("lang")
    @api.depends(
        "order_line.price_subtotal",
        "currency_id",
        "company_id",
        "payment_term_id",
    )
    def _compute_tax_totals(self):
        res = super()._compute_tax_totals()
        for order in self:
            if (
                order.company_id.account_fiscal_country_id.code != "VE"
                or not order.tax_totals
            ):
                continue
            order.tax_totals["same_tax_base"] = False
            for subtotal in order.tax_totals.get("subtotals", []):
                for tax_group in subtotal.get("tax_groups", []):
                    if tax_group.get("display_base_amount_currency") is False:
                        tax_group["display_base_amount_currency"] = tax_group.get(
                            "base_amount_currency", 0.0
                        )
                    if tax_group.get("display_base_amount") in (False, None):
                        tax_group["display_base_amount"] = tax_group.get(
                            "base_amount", 0.0
                        )
        return res

    @api.model
    def _cron_create_uninvoiced_orders_announcement(self):
        if not self.env["ir.module.module"].search(
            [("name", "=", "announcement"), ("state", "=", "installed")], limit=1
        ):
            return
        orders = self.search(
            [("state", "=", "sale"), ("invoice_status", "=", "to invoice")]
        )
        if not orders:
            return
        group_sales = self.env.ref("sales_team.group_sale_salesman", raise_if_not_found=False)
        group_invoice = self.env.ref("account.group_account_invoice", raise_if_not_found=False)
        if not group_sales or not group_invoice:
            return
        allowed_users = group_sales.users & group_invoice.users
        if not allowed_users:
            return
        action_orders = self.env.ref(
            "l10n_ve_seniat_sale.action_sale_order_to_invoice", raise_if_not_found=False
        )
        action_lines = self.env.ref(
            "l10n_ve_seniat_sale.action_sale_order_line_to_invoice", raise_if_not_found=False
        )
        base_url = self.env.company.get_base_url()
        btn_orders = ""
        btn_lines = ""
        if action_orders:
            btn_orders = f'<a href="{base_url}/web#action={action_orders.id}&model=sale.order&view_type=list" class="btn btn-primary">Ver pedidos pendientes</a>'
        if action_lines:
            btn_lines = f'<a href="{base_url}/web#action={action_lines.id}&model=sale.order.line&view_type=list" class="btn btn-secondary">Ver productos pendientes</a>'
        content = f"""
        <p>Tienes <strong>{len(orders)}</strong> pedido(s) de venta pendiente(s) de facturar.</p>
        <p>{btn_orders} {btn_lines}</p>
        """
        existing = self.env["announcement"].search(
            [
                ("name", "=", "Pedidos de venta pendientes de facturar"),
                ("active", "=", True),
            ],
            limit=1,
        )
        vals = {
            "name": "Pedidos de venta pendientes de facturar",
            "content": content,
            "announcement_type": "specific_users",
            "specific_user_ids": [(6, 0, allowed_users.ids)],
            "notification_date": fields.Datetime.now(),
            "active": True,
        }
        if existing:
            existing.write(vals)
        else:
            self.env["announcement"].create(vals)
