Venezuelan invoices and tax documents need the fiscal address of the
customer, which includes its municipality and parish. This data used to live
inside `l10n_ve_seniat`. It is now a separate module so that other modules can
use Venezuelan addresses without the whole SENIAT accounting localization.

Databases that already had `l10n_ve_seniat` keep their states,
municipalities, parishes and the values set on contacts: when this module is
installed, it takes ownership of those records instead of creating new ones.
