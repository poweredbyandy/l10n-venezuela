def migrate(cr, version):
    cr.execute(
        """
        UPDATE account_move AS move
           SET l10n_ve_legacy_company_discount_totals = TRUE
          FROM res_company AS company
         WHERE company.id = move.company_id
           AND move.currency_id != company.currency_id
           AND move.state IN ('posted', 'cancel')
           AND move.move_type IN (
               'out_invoice', 'out_refund', 'out_receipt',
               'in_invoice', 'in_refund', 'in_receipt'
           )
        """
    )
