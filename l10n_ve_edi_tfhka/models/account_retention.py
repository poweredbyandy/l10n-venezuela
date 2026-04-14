import re

from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountRetention(models.Model):
    _inherit = "account.retention"

    def _tfhka_retention_serie_from_move(self, move):
        self.ensure_one()
        return re.sub(r"[^0-9A-Za-z]", "", (move.journal_id.series_correlative or "").strip())[:20]

    def _tfhka_retention_document_number_from_move(self, move):
        self.ensure_one()
        if hasattr(move, "_tfhka_get_document_number"):
            return move._tfhka_get_document_number()
        return re.sub(r"[^0-9]", "", move.name or "")[:19]

    def _tfhka_retention_format_date(self, dt):
        self.ensure_one()
        date_val = dt or fields.Date.context_today(self)
        return fields.Date.to_date(date_val).strftime("%d/%m/%Y")

    def _tfhka_build_apply_retention_documents(self):
        self.ensure_one()
        if not self.retention_line_ids:
            raise UserError(_("La retencion no tiene lineas para construir el payload EDI."))

        by_move = {}
        for line in self.retention_line_ids.filtered(lambda l: l.move_id):
            move = line.move_id
            if move.id not in by_move:
                by_move[move.id] = {
                    "move": move,
                    "base": 0.0,
                    "iva": 0.0,
                    "ret": 0.0,
                }
            by_move[move.id]["base"] += abs(line.invoice_amount or 0.0)
            by_move[move.id]["iva"] += abs(line.iva_amount or 0.0)
            by_move[move.id]["ret"] += abs(line.retention_amount or 0.0)

        if not by_move:
            raise UserError(_("No hay lineas de retencion con factura asociada."))

        docs = []
        for vals in by_move.values():
            move = vals["move"]
            if not move.l10n_ve_control_number:
                raise UserError(
                    _(
                        "La factura %(move)s no tiene numero de control; no se puede aplicar retencion en TFHKA.",
                        move=move.display_name,
                    )
                )
            docs.append(
                {
                    "serie": self._tfhka_retention_serie_from_move(move) or "",
                    "numeroDocumento": self._tfhka_retention_document_number_from_move(move),
                    "numeroControl": move.l10n_ve_control_number,
                    "totalRetencion": {
                        "totalBaseImponible": self._l10n_ve_edi_format_decimal(vals["base"]),
                        "numeroCompRetencion": self.number or self.name or str(self.id),
                        "fechaEmisionCR": self._tfhka_retention_format_date(self.date),
                        "totalIVA": self._l10n_ve_edi_format_decimal(vals["iva"]),
                        "totalRetenido": self._l10n_ve_edi_format_decimal(vals["ret"]),
                    },
                }
            )
        return docs

    def _l10n_ve_edi_build_payload_for_provider(self, provider):
        self.ensure_one()
        if provider == "tfhka":
            return {"documentosRetencion": self._tfhka_build_apply_retention_documents()}
        return super()._l10n_ve_edi_build_payload_for_provider(provider)

    def _l10n_ve_edi_dispatch_payload(self, payload):
        self.ensure_one()
        provider = self._l10n_ve_edi_get_provider()
        if provider != "tfhka":
            return super()._l10n_ve_edi_dispatch_payload(payload)

        params = self.env["ir.config_parameter"].sudo()
        username = params.get_param("l10n_ve_edi_tfhka.username")
        password = params.get_param("l10n_ve_edi_tfhka.password")
        if not username or not password:
            return {"success": False, "error": _("Credenciales TFHKA no configuradas.")}

        client = self.env["l10n_ve_edi_tfhka.api.service"].sudo()
        try:
            auth = client.authenticate(username, password)
            token = auth.get("token")
            if not token:
                return {"success": False, "error": _("La API TFHKA no devolvio token JWT.")}

            docs = (payload or {}).get("documentosRetencion") or []
            responses = []
            for doc in docs:
                resp = client.apply_retention(doc, token)
                responses.append(
                    {
                        "numeroDocumento": doc.get("numeroDocumento"),
                        "numeroControl": doc.get("numeroControl"),
                        "respuesta": resp,
                    }
                )
            return {"success": True, "response": {"resultados": responses}}
        except UserError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
