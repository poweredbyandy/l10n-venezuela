from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    if version is None:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cron = env.ref(
        "l10n_ve_seniat_sale.ir_cron_sale_order_to_invoice_announcement",
        raise_if_not_found=False,
    )
    if cron:
        cron.unlink()
    if "announcement" in env.registry:
        env["announcement"].search(
            [("name", "=", "Pedidos de venta pendientes de facturar")]
        ).unlink()
    for xmlid in (
        "l10n_ve_seniat_sale.action_sale_order_to_invoice",
        "l10n_ve_seniat_sale.action_sale_order_line_to_invoice",
    ):
        action = env.ref(xmlid, raise_if_not_found=False)
        if action:
            action.unlink()
