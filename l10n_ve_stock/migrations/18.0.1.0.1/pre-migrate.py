def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'res_company'
          AND column_name = 'l10n_ve_dispatch_guide_section_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'stock_warehouse'
          AND column_name = 'l10n_ve_dispatch_guide_section_id'
        """
    )
    if not cr.fetchone():
        cr.execute(
            """
            ALTER TABLE stock_warehouse
            ADD COLUMN l10n_ve_dispatch_guide_section_id INTEGER
            """
        )
    cr.execute(
        """
        UPDATE stock_warehouse sw
        SET l10n_ve_dispatch_guide_section_id = rc.l10n_ve_dispatch_guide_section_id
        FROM res_company rc
        WHERE sw.company_id = rc.id
          AND rc.l10n_ve_dispatch_guide_section_id IS NOT NULL
        """
    )
