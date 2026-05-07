from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ve_fiscal_serial_flag_21 = fields.Selection(
        selection=[
            ("30", "30"),
            ("00", "00"),
            ("01", "01"),
            ("02", "02"),
        ],
        string="FLAG 21 fiscal",
        default="30",
        required=True,
        help="Define la FLAG_21 base para comandos fiscales en WebSerial.",
    )

    l10n_ve_fiscal_serial_use_emulator = fields.Boolean(
        string="Usando emulador fiscal",
        help=(
            "Si está activo, el flujo de impresión fiscal por WebSerial "
            "omite la consulta previa de estado de la impresora."
        ),
    )
    l10n_ve_fiscal_serial_send_default_code_in_name = fields.Boolean(
        string="Enviar codigo en nombre de producto",
        help=(
            "Si está activo y la línea tiene codigo interno, el nombre enviado "
            "a la máquina fiscal será: [CODIGO] Producto."
        ),
    )

    @api.model
    def l10n_ve_fiscal_serial_get_machine_config(self):
        company = self.env.company
        return {
            "flag_21": company.l10n_ve_fiscal_serial_flag_21 or "30",
            "use_emulator": bool(company.l10n_ve_fiscal_serial_use_emulator),
            "send_default_code_in_name": bool(
                company.l10n_ve_fiscal_serial_send_default_code_in_name
            ),
        }
