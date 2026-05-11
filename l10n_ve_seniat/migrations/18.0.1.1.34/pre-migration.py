def migrate(cr, version):
    cr.execute(
        """
        UPDATE res_company
           SET chart_template = 've_seniat_basic'
         WHERE chart_template = 've_seniat_empty'
        """
    )
