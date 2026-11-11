from odoo import _, fields, models
from odoo.exceptions import UserError

from .client import (
    ICP_API_ENVIRONMENT,
    ICP_BASE_URL,
    ICP_PASSWORD_PRODUCTION,
    ICP_PASSWORD_TEST,
    ICP_PRODUCTION_URL,
    ICP_TEST_URL,
    ICP_USERNAME_PRODUCTION,
    ICP_USERNAME_TEST,
    TFHKA_API_URL_TEST,
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    tfhka_api_environment = fields.Selection(
        [
            ("test", "Pruebas"),
            ("production", "Producción"),
        ],
        string="Ambiente HKA",
        default="test",
        config_parameter=ICP_API_ENVIRONMENT,
    )
    tfhka_test_url = fields.Char(
        string="URL de pruebas",
        default=TFHKA_API_URL_TEST,
        config_parameter=ICP_TEST_URL,
    )
    tfhka_production_url = fields.Char(
        string="URL de producción",
        config_parameter=ICP_PRODUCTION_URL,
    )
    tfhka_username_test = fields.Char(
        string="Usuario de pruebas",
        config_parameter=ICP_USERNAME_TEST,
    )
    tfhka_password_test = fields.Char(
        string="Clave de pruebas",
        config_parameter=ICP_PASSWORD_TEST,
    )
    tfhka_username_production = fields.Char(
        string="Usuario de producción",
        config_parameter=ICP_USERNAME_PRODUCTION,
    )
    tfhka_password_production = fields.Char(
        string="Clave de producción",
        config_parameter=ICP_PASSWORD_PRODUCTION,
    )
    tfhka_iva_supplier_retention_edi_serie = fields.Char(
        related="company_id.iva_supplier_retention_journal_id.l10n_ve_edi_tfhka_serie",
        string="IVA TFHKA series",
        readonly=False,
    )
    tfhka_iva_supplier_retention_edi_sucursal = fields.Char(
        related=(
            "company_id.iva_supplier_retention_journal_id.l10n_ve_edi_tfhka_sucursal"
        ),
        string="IVA TFHKA establishment",
        readonly=False,
    )
    tfhka_islr_supplier_retention_edi_serie = fields.Char(
        related="company_id.islr_supplier_retention_journal_id.l10n_ve_edi_tfhka_serie",
        string="ISLR TFHKA series",
        readonly=False,
    )
    tfhka_islr_supplier_retention_edi_sucursal = fields.Char(
        related=(
            "company_id.islr_supplier_retention_journal_id.l10n_ve_edi_tfhka_sucursal"
        ),
        string="ISLR TFHKA establishment",
        readonly=False,
    )

    def _tfhka_selected_credentials(self):
        self.ensure_one()
        if self.tfhka_api_environment == "production":
            return (
                self.tfhka_username_production,
                self.tfhka_password_production,
                (self.tfhka_production_url or "").strip().rstrip("/"),
            )
        return (
            self.tfhka_username_test,
            self.tfhka_password_test,
            (self.tfhka_test_url or TFHKA_API_URL_TEST).strip().rstrip("/"),
        )

    def set_values(self):
        res = super().set_values()
        icp = self.env["ir.config_parameter"].sudo()
        if self.tfhka_api_environment == "production":
            production_url = (self.tfhka_production_url or "").strip().rstrip("/")
            if not production_url:
                raise UserError(
                    _(
                        "Indique la URL de producción de The Factory HKA o seleccione "
                        "el ambiente Pruebas."
                    )
                )
            icp.set_param(ICP_BASE_URL, production_url)
        else:
            test_url = (self.tfhka_test_url or TFHKA_API_URL_TEST).strip().rstrip("/")
            icp.set_param(ICP_BASE_URL, test_url)
        return res

    def action_test_tfhka_connection(self):
        self.ensure_one()
        username, password, base_url = self._tfhka_selected_credentials()
        if not username or not password:
            raise UserError(_("TFHKA username and password are required."))
        if not base_url:
            raise UserError(_("Indique la URL del ambiente TFHKA seleccionado."))
        client = (
            self.env["l10n_ve_edi_tfhka.api.service"]
            .sudo()
            .with_context(tfhka_base_url=base_url)
        )
        client.authenticate(username, password)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Connection with The Factory HKA was successful."),
                "type": "success",
                "sticky": False,
            },
        }
