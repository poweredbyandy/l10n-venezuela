During a tax audit, SENIAT officers ask for access to the accounting
records. This module provides a dedicated user for them. It used to be created
by `l10n_ve_seniat`; it is now optional.

Databases that already had the SENIAT user keep it as it was. When this
module is installed, it takes over the existing user and contact, loads its
data and then restores their active state, groups and contact data. The
password is never changed. If a user with login `seniat` exists without an
external id, it is reused instead of creating a new one.
