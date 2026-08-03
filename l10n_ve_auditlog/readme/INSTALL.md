Do not install this module together with OCA ``auditlog``. Both modules
define the same models (``auditlog.*``).

If you are migrating from OCA ``auditlog``:

1. Uninstall OCA ``auditlog`` (or remove it from the addons path after
   backing up the database).
2. Install or upgrade ``l10n_ve_auditlog``.
3. Upgrade ``l10n_ve_audit`` (compatibility bridge).

If you already had ``l10n_ve_audit`` installed, upgrade both modules. A
pre-migration script moves XML IDs from ``l10n_ve_audit`` to
``l10n_ve_auditlog``.

Review subscribed rules and security groups after the migration.
