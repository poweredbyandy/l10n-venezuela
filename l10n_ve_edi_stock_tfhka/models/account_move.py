import base64
import binascii
import json
import re

from odoo import models

from odoo.addons.l10n_ve_edi.models.edi_mixin import STATE_SENT


class AccountMove(models.Model):
    _inherit = "account.move"

    def _tfhka_get_dispatch_pickings_for_factura_guia(self):
        self.ensure_one()
        pickings = self.picking_ids
        if not pickings and self.invoice_origin:
            sale = self.env["sale.order"].search(
                [
                    ("name", "=", self.invoice_origin),
                    ("company_id", "=", self.company_id.id),
                ],
                limit=1,
            )
            if sale:
                pickings = sale.picking_ids
        return pickings.filtered(
            lambda picking: picking.state == "done"
            and picking._l10n_ve_is_ve_outgoing_dispatch_guide_picking()
            and picking._l10n_ve_edi_dispatch_guide_qualifies_for_factura_guia()
            and picking.sale_id
            and picking.sale_id.journal_id == self.journal_id
        ).sorted("id")

    def _tfhka_build_factura_guia(self):
        self.ensure_one()
        if self.move_type != "out_invoice":
            return None
        rows = []
        for picking in self._tfhka_get_dispatch_pickings_for_factura_guia()[:5]:
            if hasattr(picking, "_tfhka_get_document_number_for_reference"):
                numero = picking._tfhka_get_document_number_for_reference()
                serie = (
                    picking._tfhka_get_serie()
                    if hasattr(picking, "_tfhka_get_serie")
                    else ""
                )
            elif hasattr(picking, "_tfhka_get_document_number"):
                numero = picking._tfhka_get_document_number()
                serie = picking._tfhka_get_serie() or ""
            else:
                serie = ""
                numero = re.sub(r"\D", "", picking.name or str(picking.id or ""))
            numero = (numero or "").strip()
            if not numero:
                continue
            rows.append(
                {
                    "tipoDocumento": "04",
                    "serie": re.sub(r"[^0-9A-Za-z]", "", serie)[:20],
                    "numeroDocumento": numero[:19],
                }
            )
        return rows or None

    def _tfhka_refresh_invoice_payload_factura_guia_before_send(self):
        self.ensure_one()
        if self.move_type != "out_invoice":
            return
        attachment = self.l10n_ve_edi_payload_attachment_id
        if not attachment or not attachment.datas:
            return
        try:
            payload = json.loads(base64.b64decode(attachment.datas).decode("utf-8"))
        except (json.JSONDecodeError, TypeError, ValueError, binascii.Error):
            return
        factura_guia = self._tfhka_build_factura_guia()
        if not factura_guia:
            return
        encabezado = payload.setdefault("documentoElectronico", {}).setdefault(
            "encabezado", {}
        )
        if encabezado.get("facturaGuia") == factura_guia:
            return
        encabezado["facturaGuia"] = factura_guia
        new_attachment = self._l10n_ve_edi_create_payload_attachment(payload)
        self.write({"l10n_ve_edi_payload_attachment_id": new_attachment.id})

    def _run_job(self):
        self.ensure_one()
        if self.journal_id.l10n_ve_edi_provider == "tfhka":
            self._tfhka_refresh_invoice_payload_factura_guia_before_send()
        result = super()._run_job()
        if (
            result
            and self.move_type == "out_invoice"
            and self.journal_id.l10n_ve_edi_provider == "tfhka"
            and self.l10n_ve_edi_send_state == STATE_SENT
        ):
            self._l10n_ve_edi_tfhka_sync_dispatch_guides_with_invoice()
        return result

    def _l10n_ve_edi_tfhka_sync_dispatch_guides_with_invoice(self):
        self.ensure_one()
        if (
            self.move_type != "out_invoice"
            or self.state != "posted"
            or self.journal_id.l10n_ve_edi_provider != "tfhka"
            or self.l10n_ve_edi_send_state != "sent"
        ):
            return
        pickings = self._tfhka_get_dispatch_pickings_for_factura_guia().filtered(
            lambda picking: picking.l10n_ve_edi_send_state == "sent"
        )
        for picking in pickings:
            picking._l10n_ve_edi_tfhka_resend_with_invoice_links(self)
