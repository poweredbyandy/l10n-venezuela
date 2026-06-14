import re

from odoo import api, fields, models


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
    def _tfhka_build_secuencia_yyyy_mm_seq(self, ref_date, name, record_id):
        if not ref_date:
            ref_date = fields.Date.context_today(self)
        elif hasattr(ref_date, "date"):
            ref_date = ref_date.date()
        seq_int = self._tfhka_parse_sequence_from_odoo_name(name, record_id)
        if seq_int == 0:
            seq_int = record_id or 0
        return f"{ref_date.year}{ref_date.month:02d}{int(seq_int):06d}"
