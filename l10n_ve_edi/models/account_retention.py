import base64
import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .edi_mixin import STATE_FAILED, STATE_QUEUED, STATE_SENT


class AccountRetention(models.Model):
    _name = "account.retention"
    _inherit = ["account.retention", "l10n_ve.edi.mixin"]

    l10n_ve_edi_show_tab = fields.Boolean(
        compute="_compute_l10n_ve_edi_show_tab",
        depends=[
            "type_retention",
            "retention_line_ids",
            "retention_line_ids.move_id.journal_id.l10n_ve_edi_provider",
        ],
        string="Show EDI Tab",
    )

    def _l10n_ve_edi_get_provider(self):
        self.ensure_one()
        providers = set(
            self.retention_line_ids.mapped("move_id.journal_id.l10n_ve_edi_provider")
        )
        providers.discard(False)
        providers.discard("none")
        if len(providers) > 1:
            raise ValidationError(
                _(
                    "Las lineas de retencion apuntan a facturas con mas de un proveedor EDI. "
                    "Debe separar la retencion por proveedor."
                )
            )
        return next(iter(providers), False)

    def _compute_l10n_ve_edi_show_tab(self):
        for record in self:
            provider = False
            if record.type_retention == "iva" and record.retention_line_ids:
                providers = set(
                    record.retention_line_ids.mapped("move_id.journal_id.l10n_ve_edi_provider")
                )
                providers.discard(False)
                providers.discard("none")
                provider = next(iter(providers), False) if len(providers) == 1 else False
            record.l10n_ve_edi_show_tab = bool(provider)

    def _l10n_ve_edi_is_retention_target(self):
        self.ensure_one()
        return (
            self.country_code == "VE"
            and self.state == "emitted"
            and self.type_retention == "iva"
            and bool(self._l10n_ve_edi_get_provider())
        )

    def _l10n_ve_edi_create_payload_attachment(self, payload):
        self.ensure_one()
        filename = (self.number or self.name or f"retention_{self.id}").replace("/", "_")
        content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        datas = base64.b64encode(content.encode("utf-8"))
        return self.env["ir.attachment"].sudo().create(
            {
                "name": f"l10n_ve_edi_retention_payload_{filename}.json",
                "type": "binary",
                "datas": datas,
                "mimetype": "application/json",
                "res_model": self._name,
                "res_id": self.id,
            }
        )

    def _build_payload_to_send(self):
        self.ensure_one()
        provider = self._l10n_ve_edi_get_provider()
        if not provider:
            raise UserError(
                _(
                    "No se detecto proveedor EDI en las facturas asociadas a la retencion. "
                    "Revise los diarios de esas facturas."
                )
            )
        return self._l10n_ve_edi_build_payload_for_provider(provider)

    def _l10n_ve_edi_build_payload_for_provider(self, provider):
        self.ensure_one()
        raise UserError(
            _(
                "No hay modulo instalado para el proveedor EDI %(code)s en retenciones."
            )
            % {"code": provider}
        )

    def _l10n_ve_edi_dispatch_payload(self, payload):
        self.ensure_one()
        provider = self._l10n_ve_edi_get_provider()
        return {
            "success": False,
            "error": (
                "Proveedor EDI no soportado para retencion: %(provider)s."
                % {"provider": provider or "none"}
            ),
        }

    def _l10n_ve_edi_on_dispatch_success(self, response):
        self.ensure_one()

    def _l10n_ve_edi_enqueue_send(self, reuse_payload=False):
        self.ensure_one()
        attachment = self.l10n_ve_edi_payload_attachment_id if reuse_payload else False
        if not attachment:
            payload = self._build_payload_to_send()
            attachment = self._l10n_ve_edi_create_payload_attachment(payload)
        self.write(
            {
                "l10n_ve_edi_payload_attachment_id": attachment.id,
                "l10n_ve_edi_send_state": STATE_QUEUED,
                "l10n_ve_edi_last_error": False,
                "l10n_ve_edi_response_json": False,
            }
        )
        self.message_post(body=_("Solicitud de envio EDI de retencion encolada."))
        self.with_delay(
            description=f"EDI VE send retention {self.number or self.id}",
            channel="root",
        )._job_l10n_ve_edi_send_retention(self.id)

    def action_l10n_ve_edi_send(self):
        for retention in self:
            if not retention._l10n_ve_edi_is_retention_target():
                raise UserError(
                    _(
                        "La retencion debe estar emitida, ser IVA y tener proveedor EDI en las facturas asociadas."
                    )
                )
            if retention.l10n_ve_edi_send_state == STATE_QUEUED:
                raise UserError(_("Ya hay un envio EDI en cola para esta retencion."))
            if retention.l10n_ve_edi_send_state == STATE_SENT:
                raise UserError(_("La retencion ya fue enviada por EDI."))
            retention._l10n_ve_edi_enqueue_send(reuse_payload=False)
        return True

    def action_l10n_ve_edi_retry_send(self):
        return self.action_l10n_ve_edi_send()

    def _run_edi_retention_job(self):
        self.ensure_one()
        attachment = self.l10n_ve_edi_payload_attachment_id
        error_message = False
        if not attachment or not attachment.datas:
            error_message = _("Falta el adjunto con el payload EDI de retencion.")
        else:
            payload = json.loads(base64.b64decode(attachment.datas).decode("utf-8"))
            dispatch = self._l10n_ve_edi_dispatch_payload(payload)
            if dispatch.get("success"):
                response = dispatch.get("response")
                response_json = (
                    json.dumps(response, ensure_ascii=False, indent=2)
                    if response is not None
                    else False
                )
                self.write(
                    {
                        "l10n_ve_edi_send_state": STATE_SENT,
                        "l10n_ve_edi_sent_at": fields.Datetime.now(),
                        "l10n_ve_edi_last_error": False,
                        "l10n_ve_edi_response_json": response_json,
                    }
                )
                self._l10n_ve_edi_on_dispatch_success(response)
                self.message_post(body=_("Retencion enviada exitosamente por EDI."))
                return True
            error_message = dispatch.get("error") or _(
                "El conector EDI no completo el envio de la retencion."
            )
        if error_message:
            self.write(
                {
                    "l10n_ve_edi_send_state": STATE_FAILED,
                    "l10n_ve_edi_last_error": error_message,
                }
            )
            self.message_post(body=_("Fallo el envio EDI de retencion: %s") % error_message)
        return False

    @api.model
    def _job_l10n_ve_edi_send_retention(self, retention_id):
        retention = self.sudo().browse(retention_id).exists()
        if not retention:
            return False
        return retention._run_edi_retention_job()
