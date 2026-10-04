# Part of Odoo. See LICENSE file for full copyright and licensing details.

import re

from odoo import _, api, models
from odoo.exceptions import ValidationError

VE_CODE = "VE"
VE_VAT_REGEX = re.compile(
    r"""
    ^([vecjpg])                          # group 1 - kind
    (
        (?:
            (?P<optional_1>-)?                  # optional '-' (1)
            [0-9]{2}
            (?(optional_1)(?P<optional_2>[.])?) # optional '.' (2) only if (1)
            [0-9]{3}
            (?(optional_2)[.])                  # mandatory '.' if (2)
            [0-9]{3}
            (?(optional_1)-)                    # mandatory '-' if (1)
        |
            [0-9]{7}                            # cédula compacta (ej. V7440703)
        )
    )                                       # group 2 - identifier number
    ([0-9])?                                # dígito verificador opcional
    $
""",
    re.VERBOSE | re.IGNORECASE,
)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _l10n_ve_validate_partner_vat_format_enabled(self):
        return self.env.company.l10n_ve_validate_partner_vat_format

    def _l10n_ve_must_check_rif_vat_format(self):
        self.ensure_one()
        if self.env.context.get("skip_l10n_ve_vat_rif_format_check"):
            return False
        if not self._l10n_ve_validate_partner_vat_format_enabled():
            return False
        commercial = self.commercial_partner_id
        return (
            self.customer_rank > 0
            or self.supplier_rank > 0
            or commercial.customer_rank > 0
            or commercial.supplier_rank > 0
        )

    def _l10n_ve_skip_base_vat_check(self):
        self.ensure_one()
        country = self.commercial_partner_id.country_id
        return country.code == VE_CODE and not self._l10n_ve_must_check_rif_vat_format()

    def check_vat_ve(self, vat):
        """Valida formato de RIF/CI venezolano.

        Parameters
        ----------
        vat : str
            Identificación fiscal a validar.

        Returns
        -------
        bool

        Notes
        -----
        Art. 13 num. 5-7 PA SNAT/2011/0071: RIF del emisor y adquiriente.
        Art. 7 num. 3 y 7 PA SNAT/2024/000102: datos del receptor digital.
        """

        return super().check_vat_ve(vat) or bool(VE_VAT_REGEX.fullmatch(vat))

    @api.constrains("vat", "country_id")
    def check_vat(self):
        partners = self.filtered(
            lambda partner: not partner._l10n_ve_skip_base_vat_check()
        )
        return super(ResPartner, partners).check_vat()

    @api.constrains("vat", "country_id", "customer_rank", "supplier_rank")
    def _check_l10n_ve_vat_format(self):
        """Restricción ORM sobre formato de RIF en contactos venezolanos.

        Notes
        -----
        Art. 13 num. 5-7 PA SNAT/2011/0071: RIF en facturas.
        """

        for partner in self:
            if not partner.country_id or partner.country_id.code != VE_CODE:
                continue
            if not partner._l10n_ve_must_check_rif_vat_format():
                continue
            vat = (partner.vat or "").strip()
            if not vat or vat == "/":
                continue
            if not partner.check_vat_ve(vat):
                raise ValidationError(
                    _(
                        "El RIF («%(vat)s») no tiene un formato válido para contactos "
                        "venezolanos. Use [V/E/J/C/P/G] y el número (ej.: V7440703, "
                        "V12345678, J-12.345.678-9)."
                    )
                    % {"vat": vat}
                )
