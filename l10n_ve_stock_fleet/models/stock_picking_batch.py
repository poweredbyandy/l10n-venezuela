from odoo import api, fields, models


class StockPickingBatch(models.Model):
    _inherit = "stock.picking.batch"

    l10n_ve_own_fleet = fields.Boolean(
        related="company_id.l10n_ve_own_fleet",
    )
    l10n_ve_transport_partner_id = fields.Many2one(
        "res.partner",
        string="Transportista",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    l10n_ve_fleet_vehicle_id = fields.Many2one(
        "fleet.vehicle",
        string="Vehículo",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    @api.model_create_multi
    def create(self, vals_list):
        batches = super().create(vals_list)
        batches._l10n_ve_apply_fleet_to_pickings()
        return batches

    def write(self, vals):
        res = super().write(vals)
        watched = {"l10n_ve_transport_partner_id", "l10n_ve_fleet_vehicle_id"}
        if watched.intersection(vals) or "picking_ids" in vals:
            self._l10n_ve_apply_fleet_to_pickings()
        return res

    def _l10n_ve_apply_fleet_to_pickings(self):
        for batch in self.filtered("l10n_ve_own_fleet"):
            pickings = batch.picking_ids.filtered(
                lambda picking: picking.state not in ("done", "cancel")
            )
            if not pickings:
                continue
            pickings.write(
                {
                    "l10n_ve_transport_partner_id": batch.l10n_ve_transport_partner_id.id,
                    "l10n_ve_fleet_vehicle_id": batch.l10n_ve_fleet_vehicle_id.id,
                }
            )
