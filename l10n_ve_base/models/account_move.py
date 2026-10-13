from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ve_invoice_date = fields.Datetime(
        string="Fecha del documento",
        copy=False,
        tracking=True,
        help=(
            "Forma libre: si está vacía se asigna al confirmar; si ya tiene fecha se "
            "mantiene. Contingencia: indíquela antes de confirmar. Facturación "
            "digital: fecha de sincronización con la imprenta. Máquina fiscal: fecha "
            "en que se imprimió el documento."
        ),
    )
    l10n_ve_control_number = fields.Char(
        string="Control Number",
        copy=False,
        store=True,
        tracking=True,
    )
    l10n_ve_serial_number = fields.Char(
        string="Fiscal Machine Serial",
        copy=False,
        tracking=True,
        help="Serial number of the fiscal machine",
    )
    l10n_ve_invoice_number = fields.Char(
        string="Fiscal Invoice Number",
        copy=False,
        tracking=True,
        help="Invoice number from the fiscal machine",
    )
    l10n_ve_report_z = fields.Char(
        string="Report Z Number",
        copy=False,
        tracking=True,
        help="Report Z number from the fiscal machine",
    )
    l10n_ve_on_behalf_of_third_party = fields.Boolean(
        string="Indicador por cuenta de terceros",
        compute="_compute_l10n_ve_on_behalf_of_third_party",
        store=True,
        copy=False,
        help=(
            "Verdadero si hay un contacto en Por cuenta de Terceros en "
            "facturas de cliente. Según Art. 11 PA00071, esas operaciones "
            "deben emitirse en forma libre."
        ),
    )
    l10n_ve_third_party_partner_id = fields.Many2one(
        "res.partner",
        string="Por cuenta de Terceros",
        copy=False,
        ondelete="restrict",
    )
    l10n_ve_journal_emission_medium = fields.Selection(
        related="journal_id.l10n_ve_emission_medium",
        string="Medio de emisión (diario)",
        readonly=True,
    )

    @api.depends("l10n_ve_third_party_partner_id", "move_type")
    def _compute_l10n_ve_on_behalf_of_third_party(self):
        """Marca documentos emitidos por cuenta de terceros.

        Notes
        -----
        Art. 10 Decreto con Rango, Valor y Fuerza de Ley del IVA.
        Art. 11 y Art. 32 PA SNAT/2011/0071: deben emitirse en forma libre.
        """

        for move in self:
            move.l10n_ve_on_behalf_of_third_party = bool(
                move.l10n_ve_third_party_partner_id
                and move.move_type in ("out_invoice", "out_refund")
            )
