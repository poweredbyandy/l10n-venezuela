# Part of Odoo. See LICENSE file for full copyright and licensing details.

DB_AUDIT_TABLE_XMLIDS = {
    "account_move": "db_audit_table_account_move",
    "account_account": "db_audit_table_account_account",
    "account_journal": "db_audit_table_account_journal",
    "account_tax": "db_audit_table_account_tax",
    "res_currency_rate": "db_audit_table_res_currency_rate",
    "ir_sequence": "db_audit_table_ir_sequence",
    "tax_unit": "db_audit_table_tax_unit",
    "res_company": "db_audit_table_res_company",
    "account_payment": "db_audit_table_account_payment",
    "account_retention": "db_audit_table_account_retention",
    "account_retention_line": "db_audit_table_account_retention_line",
}


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        UPDATE ir_model_data AS src
           SET module = 'l10n_ve_auditlog'
         WHERE src.module = 'l10n_ve_audit'
           AND src.name != 'module_l10n_ve_audit'
           AND NOT EXISTS (
                SELECT 1
                  FROM ir_model_data AS dst
                 WHERE dst.module = 'l10n_ve_auditlog'
                   AND dst.name = src.name
           )
        """
    )
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
              FROM information_schema.tables
             WHERE table_schema = 'public'
               AND table_name = 'l10n_ve_db_audit_table'
        )
        """
    )
    if not cr.fetchone()[0]:
        return
    for table_name, xmlid_name in DB_AUDIT_TABLE_XMLIDS.items():
        cr.execute(
            """
            SELECT id
              FROM l10n_ve_db_audit_table
             WHERE table_name = %s
             LIMIT 1
            """,
            (table_name,),
        )
        row = cr.fetchone()
        if not row:
            continue
        res_id = row[0]
        cr.execute(
            """
            SELECT id
              FROM ir_model_data
             WHERE module = 'l10n_ve_auditlog'
               AND name = %s
             LIMIT 1
            """,
            (xmlid_name,),
        )
        if cr.fetchone():
            continue
        cr.execute(
            """
            UPDATE ir_model_data
               SET module = 'l10n_ve_auditlog',
                   res_id = %s,
                   model = 'l10n.ve.db.audit.table',
                   noupdate = TRUE
             WHERE module = 'l10n_ve_audit'
               AND name = %s
            """,
            (res_id, xmlid_name),
        )
        if cr.rowcount:
            continue
        cr.execute(
            """
            INSERT INTO ir_model_data (
                module, name, model, res_id, noupdate
            ) VALUES (
                'l10n_ve_auditlog', %s, 'l10n.ve.db.audit.table', %s, TRUE
            )
            """,
            (xmlid_name, res_id),
        )
