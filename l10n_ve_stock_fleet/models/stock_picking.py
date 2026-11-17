from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

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
        pickings = super().create(vals_list)
        pickings._l10n_ve_sync_carrier_from_fleet()
        return pickings

    def write(self, vals):
        res = super().write(vals)
        if {"l10n_ve_transport_partner_id", "l10n_ve_fleet_vehicle_id"} & set(vals):
            self._l10n_ve_sync_carrier_from_fleet()
        return res

    def _l10n_ve_sync_carrier_from_fleet(self):
        if self.env.context.get("l10n_ve_skip_carrier_sync"):
            return
        for picking in self:
            partner = picking.l10n_ve_transport_partner_id
            vehicle = picking.l10n_ve_fleet_vehicle_id
            if not picking.l10n_ve_own_fleet and not partner and not vehicle:
                continue
            values = {}
            if partner or picking.l10n_ve_own_fleet:
                values["l10n_ve_carrier_name"] = partner.name if partner else False
                values["l10n_ve_carrier_vat"] = partner.vat if partner else False
            if vehicle or picking.l10n_ve_own_fleet:
                values["l10n_ve_vehicle_plate"] = (
                    vehicle.license_plate if vehicle else False
                )
            if values:
                picking.with_context(l10n_ve_skip_carrier_sync=True).write(values)

    def _l10n_ve_dispatch_fleet_vehicle_model_name(self):
        self.ensure_one()
        vehicle = self.l10n_ve_fleet_vehicle_id
        if not vehicle or not vehicle.model_id:
            return ""
        return vehicle.model_id.display_name or vehicle.model_id.name or ""
