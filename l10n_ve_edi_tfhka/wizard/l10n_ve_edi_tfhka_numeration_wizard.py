import json

from odoo import _, api, fields, models
from odoo.exceptions import UserError

SEQUENCE_DOCUMENT_TYPES = ("01", "02", "03", "04")
NUMERATION_FOUND_CODE = 200
NUMERATION_MISSING_CODE = 201


class L10nVeEdiTfhkaNumerationWizard(models.TransientModel):
    _name = "l10n_ve_edi_tfhka.numeration.wizard"
    _description = "TFHKA numeration query and assignment"

    journal_id = fields.Many2one(
        "account.journal",
        string="Diario",
        required=True,
        domain="[('l10n_ve_edi_provider', '=', 'tfhka')]",
    )
    document_type = fields.Selection(
        [
            ("01", "Factura"),
            ("02", "Nota de crédito"),
            ("03", "Nota de débito"),
            ("04", "Guía de despacho"),
            ("05", "Comprobante de retención IVA"),
            ("06", "Comprobante de retención ISLR"),
        ],
        string="Tipo de documento",
        required=True,
        default="01",
    )
    serie = fields.Char(
        compute="_compute_serie",
        store=True,
        readonly=False,
        help="Serie enviada a TFHKA. Por defecto es la serie del diario.",
    )
    period_date = fields.Date(
        string="Periodo",
        required=True,
        default=fields.Date.context_today,
        help="Mes usado para proponer el rango de numeroDocumento.",
    )
    number_start = fields.Char(
        string="numeroDocumento desde",
        compute="_compute_number_range",
        store=True,
        readonly=False,
    )
    number_end = fields.Char(
        string="numeroDocumento hasta",
        compute="_compute_number_range",
        store=True,
        readonly=False,
    )
    numeration_state = fields.Selection(
        [
            ("draft", "Sin consultar"),
            ("available", "Con numeración disponible"),
            ("missing", "Sin numeración disponible"),
            ("assigned", "Numeración asignada"),
        ],
        string="Estado",
        default="draft",
        readonly=True,
    )
    result_message = fields.Text(string="Respuesta TFHKA", readonly=True)

    @api.depends("journal_id")
    def _compute_serie(self):
        for wizard in self:
            journal = wizard.journal_id
            wizard.serie = journal._tfhka_get_serie() if journal else ""

    @api.depends("journal_id", "document_type", "period_date")
    def _compute_number_range(self):
        mixin = self.env["l10n_ve.edi.tfhka.document.mixin"]
        for wizard in self:
            if not wizard.document_type or not wizard.period_date:
                wizard.number_start = False
                wizard.number_end = False
                continue
            yyyymm = wizard.period_date.strftime("%Y%m")
            if wizard.document_type not in SEQUENCE_DOCUMENT_TYPES:
                wizard.number_start = f"{yyyymm}{1:08d}"
                wizard.number_end = f"{yyyymm}{'9' * 8}"
                continue
            env_digit = (
                wizard.journal_id._tfhka_get_numero_documento_environment_digit()
                if wizard.journal_id
                else "0"
            )
            first_sequence = mixin._tfhka_build_secuencia_yyyy_mm_seq(
                wizard.period_date, "", 1, environment_digit=env_digit
            )
            width = 6 if env_digit == "0" else 5
            last_sequence = first_sequence[:-width] + "9" * width
            wizard.number_start = f"{wizard.document_type}{first_sequence}"
            wizard.number_end = f"{wizard.document_type}{last_sequence}"

    def _tfhka_get_client_token(self):
        params = self.env["ir.config_parameter"].sudo()
        username = params.get_param("l10n_ve_edi_tfhka.username")
        password = params.get_param("l10n_ve_edi_tfhka.password")
        if not username or not password:
            raise UserError(_("Configure usuario y clave TFHKA en Ajustes."))
        client = self.env["l10n_ve_edi_tfhka.api.service"].sudo()
        token = client.authenticate(username, password).get("token")
        if not token:
            raise UserError(_("La API TFHKA no devolvió token JWT."))
        return client, token

    def _tfhka_get_query_payload(self):
        self.ensure_one()
        return {
            "serie": self.serie or "",
            "tipoDocumento": self.document_type,
            "prefix": "",
        }

    def _tfhka_get_assign_payload(self):
        self.ensure_one()
        self._tfhka_check_number_range()
        return {
            "detalleAsignacion": [
                {
                    "serie": self.serie or "",
                    "tipoDocumento": self.document_type,
                    "numeroDocumentoInicio": self.number_start,
                    "numeroDocumentoFin": self.number_end,
                }
            ]
        }

    def _tfhka_check_number_range(self):
        self.ensure_one()
        start = (self.number_start or "").strip()
        end = (self.number_end or "").strip()
        if not start.isdigit() or not end.isdigit():
            raise UserError(
                _("El rango de numeroDocumento debe contener solo dígitos.")
            )
        if len(start) > 19 or len(end) > 19:
            raise UserError(_("NumeroDocumento admite como máximo 19 dígitos."))
        if int(start) > int(end):
            raise UserError(
                _("El numeroDocumento inicial no puede ser mayor que el final.")
            )

    def _tfhka_format_response(self, title, data):
        try:
            body = json.dumps(data, ensure_ascii=False, indent=2)
        except TypeError:
            body = str(data)
        return f"{title}\n{body}"

    def _tfhka_query_numerations(self, client, token):
        self.ensure_one()
        response = client.query_numerations(
            self._tfhka_get_query_payload(),
            token,
            extra_success_codes={NUMERATION_MISSING_CODE},
        )
        available = client._normalize_api_code(response) == NUMERATION_FOUND_CODE
        return available, response

    def _tfhka_reopen(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Numeración TFHKA"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_query(self):
        self.ensure_one()
        client, token = self._tfhka_get_client_token()
        available, response = self._tfhka_query_numerations(client, token)
        self.write(
            {
                "numeration_state": "available" if available else "missing",
                "result_message": self._tfhka_format_response(
                    _("Consulta de numeraciones:"), response
                ),
            }
        )
        return self._tfhka_reopen()

    def action_query_and_assign(self):
        self.ensure_one()
        client, token = self._tfhka_get_client_token()
        available, response = self._tfhka_query_numerations(client, token)
        if available:
            self.write(
                {
                    "numeration_state": "available",
                    "result_message": self._tfhka_format_response(
                        _("Ya existe numeración disponible; no se asignó un rango."),
                        response,
                    ),
                }
            )
            return self._tfhka_reopen()
        assign_response = client.assign_numerations(
            self._tfhka_get_assign_payload(), token
        )
        self.write(
            {
                "numeration_state": "assigned",
                "result_message": self._tfhka_format_response(
                    _("Asignación de numeraciones:"), assign_response
                ),
            }
        )
        return self._tfhka_reopen()
