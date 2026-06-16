from odoo import fields, models

from .res_partner import CUSTOMER_ADVANCE_ACCOUNT_TYPES, SUPPLIER_ADVANCE_ACCOUNT_TYPES


class ResCompany(models.Model):
    _inherit = "res.company"

    account_customer_advance_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de anticipos de cliente",
        domain=(
            f"[('account_type', 'in', {CUSTOMER_ADVANCE_ACCOUNT_TYPES}), ('deprecated', '=', False)]"
        ),
        check_company=True,
        help=(
            "Cuenta de pasivo por defecto para anticipos de clientes cuando "
            "el contacto no tiene una cuenta configurada."
        ),
    )
    account_supplier_advance_id = fields.Many2one(
        comodel_name="account.account",
        string="Cuenta de anticipos de proveedor",
        domain=(
            f"[('account_type', 'in', {SUPPLIER_ADVANCE_ACCOUNT_TYPES}), ('deprecated', '=', False)]"
        ),
        check_company=True,
        help=(
            "Cuenta de activo por defecto para anticipos a proveedores cuando "
            "el contacto no tiene una cuenta configurada."
        ),
    )
