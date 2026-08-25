def migrate(cr, version):
    replacements = (
        ("external_layout_l10n_ve_presupuesto", "web", "external_layout"),
        ("report_saleorder_document_ve", "sale", "report_saleorder_document"),
        ("quote_document_layout_preview_ve", "sale", "quote_document_layout_preview"),
    )
    for old_name, new_module, new_name in replacements:
        cr.execute(
            """
            UPDATE ir_ui_view AS child
               SET inherit_id = new_data.res_id
              FROM ir_model_data AS old_data
              JOIN ir_model_data AS new_data
                ON new_data.module = %s
               AND new_data.name = %s
               AND new_data.model = 'ir.ui.view'
             WHERE old_data.module = 'l10n_ve_seniat_sale'
               AND old_data.name = %s
               AND old_data.model = 'ir.ui.view'
               AND child.inherit_id = old_data.res_id
            """,
            (new_module, new_name, old_name),
        )
