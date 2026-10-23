# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Ajuste histórico de facturas vs auditoría de máquina fiscal.
# NO es un migration: se lanza a mano desde odoo-bin shell.
#
#   from odoo.addons.l10n_ve_fiscal_serial.tools import run_fiscal_audit_align
#   run_fiscal_audit_align(env, apply=False)           # dry-run
#   run_fiscal_audit_align(env, apply=True)             # commit
#   run_fiscal_audit_align(env, apply=True, move_names=["INV/2026/02697"])
#

from pathlib import Path


def run_fiscal_audit_align(
    env,
    apply=False,
    move_names=None,
    date_from=False,
    date_to=False,
    diff_threshold=0.01,
):
    """Align posted printed invoices to fiscal machine audit amounts.

    :param env: Odoo environment
    :param apply: False = dry-run (rollback); True = commit changes
    :param move_names: optional list of move names; empty = all candidates
    :param date_from: optional invoice_date lower bound (str YYYY-MM-DD)
    :param date_to: optional invoice_date upper bound
    :param diff_threshold: minimum absolute delta to treat as mismatch
    :return: dict with results, errors, counters
    """
    impl_path = Path(__file__).with_name("_apply_fiscal_audit_align_impl.py")
    namespace = {
        "env": env,
        "APPLY": bool(apply),
        "MOVE_NAMES": list(move_names or []),
        "DATE_FROM": date_from,
        "DATE_TO": date_to,
        "DIFF_THRESHOLD": diff_threshold,
    }
    code = compile(
        impl_path.read_text(encoding="utf-8"),
        str(impl_path),
        "exec",
    )
    exec(code, namespace)
    return {
        "results": namespace.get("results", []),
        "errors": namespace.get("errors", []),
        "skipped_no_audit": namespace.get("skipped_no_audit", 0),
    }
