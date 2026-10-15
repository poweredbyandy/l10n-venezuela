import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class L10nVeEdiTfhkaDocumentMixin(models.AbstractModel):
    _name = "l10n_ve.edi.tfhka.document.mixin"
    _description = "TFHKA numeroDocumento helpers"

    @api.model
    def _tfhka_parse_sequence_from_odoo_name(self, name, fallback_id=0):
        name = (name or "").strip()
        parts = [part.strip() for part in name.split("/") if part.strip()]
        if parts:
            seq_int = int(re.sub(r"\D", "", parts[-1]) or 0)
            if seq_int:
                return seq_int
        digits_all = re.sub(r"\D", "", name)
        if digits_all.isdigit():
            return int(digits_all)
        return int(fallback_id or 0)

    @api.model
    def _tfhka_normalize_environment_digit(self, environment_digit):
        raw = str(environment_digit if environment_digit is not None else "0").strip()
        if len(raw) == 1 and raw.isdigit():
            return raw
        return "0"

    @api.model
    def _tfhka_build_secuencia_yyyy_mm_seq(
        self, ref_date, name, record_id, environment_digit="0"
    ):
        if not ref_date:
            ref_date = fields.Date.context_today(self)
        elif hasattr(ref_date, "date"):
            ref_date = ref_date.date()
        seq_int = self._tfhka_parse_sequence_from_odoo_name(name, record_id)
        if seq_int == 0:
            seq_int = record_id or 0
        env = self._tfhka_normalize_environment_digit(environment_digit)
        yyyymm = f"{ref_date.year}{ref_date.month:02d}"
        if env == "0":
            return f"{yyyymm}{int(seq_int):06d}"
        return f"{yyyymm}{env}{int(seq_int):05d}"

    @api.model
    def _tfhka_is_foreign_buyer(self, partner):
        country = partner.country_id if partner else False
        return bool(country) and country.code != "VE"

    @api.model
    def _tfhka_get_foreign_buyer_identification(self, partner):
        id_type = re.sub(
            r"[^0-9A-Z]", "", (partner.l10n_ve_edi_tfhka_foreign_id_type or "").upper()
        )[:3]
        number = re.sub(r"[^0-9A-Za-z\-]", "", partner.vat or "").upper()
        country_code = (partner.country_id.code or "").upper()
        if country_code and number.startswith(country_code):
            number = number[len(country_code) :]
        return id_type, number[:19]

    @api.model
    def _tfhka_check_foreign_buyer_identification(self, partner):
        id_type, number = self._tfhka_get_foreign_buyer_identification(partner)
        if not id_type or not number:
            raise UserError(
                _(
                    "El comprador %(partner)s no está domiciliado en Venezuela. "
                    "Indique en el contacto el tipo de identificación extranjera "
                    "(TFHKA), por ejemplo RUT o NIT, y el número en el NIF."
                )
                % {"partner": partner.display_name}
            )
