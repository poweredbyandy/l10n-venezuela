from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    invoice_journal_id = fields.Many2one(
        comodel_name="account.journal",
        string="Diario de facturación",
        domain="[('type', '=', 'sale')]",
        check_company=True,
        help="Diario usado al facturar este pedido POS.",
    )
    l10n_ve_pos_invoice_name = fields.Char(
        related="account_move.name",
        string="Número de factura",
        readonly=True,
    )
    l10n_ve_pos_control_number = fields.Char(
        related="account_move.l10n_ve_control_number",
        string="N° de control SENIAT",
        readonly=True,
    )
    l10n_ve_pos_fiscal_invoice_number = fields.Char(
        string="N° factura máquina fiscal",
        copy=False,
    )
    l10n_ve_pos_fiscal_serial = fields.Char(
        string="Serial máquina fiscal",
        copy=False,
    )
    l10n_ve_pos_fiscal_report_z = fields.Char(
        string="N° reporte Z",
        copy=False,
    )

    def _prepare_invoice_vals(self):
        vals = super()._prepare_invoice_vals()
        if self.invoice_journal_id:
            vals["journal_id"] = self.invoice_journal_id.id
        return vals

    def _l10n_ve_pos_apply_fiscal_fields_to_move(self):
        for order in self:
            move = order.account_move
            if not move:
                continue
            vals = {}
            if (order.l10n_ve_pos_fiscal_invoice_number or "").strip() and not (
                move.l10n_ve_invoice_number or ""
            ).strip():
                vals["l10n_ve_invoice_number"] = order.l10n_ve_pos_fiscal_invoice_number
            if (order.l10n_ve_pos_fiscal_serial or "").strip() and not (
                move.l10n_ve_serial_number or ""
            ).strip():
                vals["l10n_ve_serial_number"] = order.l10n_ve_pos_fiscal_serial
            if (order.l10n_ve_pos_fiscal_report_z or "").strip() and not (
                move.l10n_ve_report_z or ""
            ).strip():
                vals["l10n_ve_report_z"] = order.l10n_ve_pos_fiscal_report_z
            if vals:
                if not move.l10n_ve_invoice_original_printed:
                    vals["l10n_ve_invoice_original_printed"] = True
                if not move.l10n_ve_invoice_date:
                    vals["l10n_ve_invoice_date"] = fields.Datetime.now()
                move.write(vals)
                if hasattr(move, "_l10n_ve_fiscal_serial_update_machine_counters"):
                    move._l10n_ve_fiscal_serial_update_machine_counters(
                        {
                            "sequence": vals.get("l10n_ve_invoice_number"),
                            "serial_machine": vals.get("l10n_ve_serial_number"),
                            "mf_reportz": vals.get("l10n_ve_report_z"),
                        }
                    )

    def _generate_pos_order_invoice(self):
        ve_orders = self.filtered(
            lambda order: order.company_id.account_fiscal_country_id.code == "VE"
        )
        other_orders = self - ve_orders

        result = False
        if other_orders:
            result = super(PosOrder, other_orders)._generate_pos_order_invoice()
        if ve_orders:
            result = super(
                PosOrder, ve_orders.with_context(generate_pdf=False)
            )._generate_pos_order_invoice()
            ve_orders._l10n_ve_pos_apply_fiscal_fields_to_move()
        return result

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        if not fields_list:
            return fields_list
        for field_name in (
            "invoice_journal_id",
            "l10n_ve_pos_fiscal_invoice_number",
            "l10n_ve_pos_fiscal_serial",
            "l10n_ve_pos_fiscal_report_z",
        ):
            if field_name not in fields_list:
                fields_list.append(field_name)
        return fields_list

    def _create_order_picking(self):
        return super(
            PosOrder, self.with_context(l10n_ve_pos_order_id=self.id)
        )._create_order_picking()
