from odoo import _, models
from odoo.exceptions import UserError


class AccountTax(models.Model):
    _inherit = "account.tax"

    def write(self, vals):
        """Impide modificar alícuotas fiscales venezolas ya configuradas.

        Notes
        -----
        Art. 13 num. 9-11 PA SNAT/2011/0071: porcentajes de IVA en facturas.
        """

        ve_taxes = self.filtered(lambda t: t.country_code == "VE")
        if ve_taxes:
            if "amount" in vals:
                raise UserError(
                    _(
                        "No está permitido modificar la alícuota de los "
                        "impuestos del país Venezuela."
                    )
                )
            if "name" in vals:
                raise UserError(
                    _(
                        "No está permitido modificar el nombre de los "
                        "impuestos del país Venezuela."
                    )
                )
        return super().write(vals)
