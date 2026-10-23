def migrate(cr, version):
    if not version:
        return
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    names = [
        "menu_queue_job_bank_auto_reconcile",
        "action_queue_job_bank_auto_reconcile",
        "job_function_reconcile_reference_batch",
        "channel_bank_auto_reconcile",
    ]
    data_records = env["ir.model.data"].search(
        [
            ("module", "=", "l10n_ve_bank_auto_reconcile"),
            ("name", "in", names),
        ]
    )
    for name in names:
        data = data_records.filtered(lambda row, name=name: row.name == name)
        if not data or data.model not in env:
            continue
        record = env[data.model].browse(data.res_id).exists()
        if record:
            record.unlink()
        else:
            data.unlink()
