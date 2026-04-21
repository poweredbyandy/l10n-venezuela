from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    l10n_ve_edi_provider = fields.Selection(
        selection_add=[("tfhka", "The Factory HKA")],
    )
    l10n_ve_edi_tfhka_serie = fields.Char(
        string="Serie (TFHKA)",
        copy=False,
        help="Debe coincidir exactamente con la serie del rango en The Factory HKA. Deje vacío para "
        "enviar serie vacía al API (numeración unificada / sin serie en HKA). Para forzar vacío si "
        "existe series_correlative en el diario, guarde un guion (-) en este campo.",
    )
    l10n_ve_edi_tfhka_sucursal = fields.Char(
        string="Sucursal / establecimiento (TFHKA)",
        size=6,
        copy=False,
        help="Código de sucursal en identificacionDocumento (máx. 6 caracteres). Debe coincidir con "
        "el rango en el portal TFHKA; si su integración válida usa sucursal vacía en el JSON, "
        "deje este campo vacío (no use 00 salvo que en HKA el rango esté dado de alta con 00).",
    )
