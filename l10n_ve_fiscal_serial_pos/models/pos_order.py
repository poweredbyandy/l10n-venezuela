from odoo import _, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    def l10n_ve_fiscal_serial_check_print_move(self):
        self.ensure_one()
        move = self.account_move
        if not move:
            raise UserError(_("La orden POS no tiene una factura contable asociada."))
        if move.country_code != "VE":
            raise UserError(_("La impresión fiscal POS solo aplica para documentos VE."))
        if move.l10n_ve_journal_emission_medium != "fiscal_machine":
            raise UserError(_("El diario del documento no está configurado como máquina fiscal."))
        if move.l10n_ve_invoice_number:
            raise UserError(_("El documento ya tiene número fiscal registrado."))

        if move.move_type == "out_invoice":
            data = move.check_print_out_invoice()
            data["l10n_ve_print_action"] = "print_out_invoice"
            return data
        if move.move_type == "out_refund":
            data = move.check_print_out_refund()
            data["l10n_ve_print_action"] = "print_out_refund"
            return data

        raise UserError(
            _("Tipo de documento %(move_type)s no soportado para impresión fiscal desde POS.")
            % {"move_type": move.move_type or ""}
        )

    def l10n_ve_fiscal_serial_register_print_result(self, values):
        self.ensure_one()
        move = self.account_move
        if not move:
            raise UserError(_("La orden POS no tiene una factura contable asociada."))

        if move.move_type == "out_invoice":
            return move.print_out_invoice(values)
        if move.move_type == "out_refund":
            return move.print_out_refund(values)

        raise UserError(
            _("Tipo de documento %(move_type)s no soportado para registrar impresión fiscal desde POS.")
            % {"move_type": move.move_type or ""}
        )
