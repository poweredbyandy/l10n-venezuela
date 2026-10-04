def migrate(cr, version):
    cr.execute(
        """
        UPDATE l10n_ve_escp_report_object
           SET expr = REGEXP_REPLACE(
                expr,
                '\\m(pl|line)\\.subtotal_company_currency\\M',
                '\\1.price_subtotal_currency',
                'g'
           )
         WHERE expr ~ '\\m(pl|line)\\.subtotal_company_currency\\M'
        """
    )
