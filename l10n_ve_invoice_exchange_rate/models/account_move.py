# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models
from odoo.tools.misc import formatLang


class AccountMove(models.Model):
    _inherit = "account.move"

    def l10n_ve_report_exchange_rate_display(self):
        """Imprime la tasa inversa con cuatro decimales.

        La moneda de la compañía suele tener dos decimales. La tasa
        guardada en la factura conserva más precisión y el documento
        fiscal debe mostrarla.
        """
        self.ensure_one()
        if not super().l10n_ve_report_exchange_rate_display():
            return False
        amount = formatLang(self.env, self.l10n_ve_inverse_rate, digits=4)
        symbol = (self.company_currency_id.symbol or "Bs").strip()
        return f"{amount} {symbol}"
