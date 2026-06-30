def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'res_company'
          AND column_name = 'l10n_ve_dispatch_guide_enabled'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        UPDATE res_company
           SET l10n_ve_dispatch_guide_enabled = TRUE
         WHERE l10n_ve_dispatch_guide_enabled IS DISTINCT FROM TRUE
        """
    )
