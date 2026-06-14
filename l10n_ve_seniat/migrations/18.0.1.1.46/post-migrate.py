def migrate(cr, version):
    cr.execute(
        """
        UPDATE account_move am
           SET l10n_ve_invoice_date = am.invoice_date::timestamp
         WHERE am.state = 'posted'
           AND am.move_type IN ('out_invoice', 'out_refund')
           AND am.l10n_ve_invoice_date IS NULL
           AND am.invoice_date IS NOT NULL
           AND EXISTS (
               SELECT 1
                 FROM res_company c
                 JOIN res_country country ON country.id = c.account_fiscal_country_id
                WHERE c.id = am.company_id
                  AND country.code = 'VE'
           )
        """
    )
