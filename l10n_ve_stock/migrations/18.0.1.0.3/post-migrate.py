def migrate(cr, version):
    cr.execute(
        """
        UPDATE report_paperformat
           SET margin_left = 0,
               margin_right = 0
         WHERE id IN (
            SELECT res_id
              FROM ir_model_data
             WHERE module = 'l10n_ve_stock'
               AND name IN (
                   'paperformat_l10n_ve_dispatch_guide_letter',
                   'paperformat_l10n_ve_dispatch_guide'
               )
         )
        """
    )
