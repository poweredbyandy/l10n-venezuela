def migrate(cr, version):
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'stock_picking'
           AND column_name = 'l10n_ve_transport_partner_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        ALTER TABLE stock_picking
            ADD COLUMN IF NOT EXISTS l10n_ve_carrier_name varchar,
            ADD COLUMN IF NOT EXISTS l10n_ve_carrier_vat varchar,
            ADD COLUMN IF NOT EXISTS l10n_ve_vehicle_plate varchar
        """
    )
    cr.execute(
        """
        UPDATE stock_picking AS picking
           SET l10n_ve_carrier_name = partner.name,
               l10n_ve_carrier_vat = partner.vat
          FROM res_partner AS partner
         WHERE picking.l10n_ve_transport_partner_id = partner.id
           AND COALESCE(picking.l10n_ve_carrier_name, '') = ''
        """
    )
    cr.execute(
        """
        SELECT 1
          FROM information_schema.columns
         WHERE table_name = 'stock_picking'
           AND column_name = 'l10n_ve_fleet_vehicle_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE stock_picking AS picking
           SET l10n_ve_vehicle_plate = vehicle.license_plate
          FROM fleet_vehicle AS vehicle
         WHERE picking.l10n_ve_fleet_vehicle_id = vehicle.id
           AND COALESCE(picking.l10n_ve_vehicle_plate, '') = ''
           AND COALESCE(vehicle.license_plate, '') != ''
        """
    )
