This module replaces OCA ``auditlog`` (same technical models ``auditlog.*``).
Do not keep both installed.

When you install or upgrade ``l10n_ve_audit`` / ``l10n_ve_auditlog`` while
OCA ``auditlog`` is present, ``pre_init_hook`` automatically:

1. Reassigns XML-IDs from ``auditlog`` to ``l10n_ve_auditlog``.
2. Marks ``auditlog`` (and modules that only depended on it) as uninstalled
   without dropping ``auditlog.*`` tables, so existing logs and rules are kept.
3. Continues with the normal install of ``l10n_ve_auditlog``.

After the upgrade, review subscribed rules and security groups.
