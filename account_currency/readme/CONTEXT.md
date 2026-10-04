In Venezuela invoices are often issued in a foreign currency, but the legal
amounts must also be shown in the company currency, with the exchange rate
used. These features used to live inside `l10n_ve_seniat`, and the manual
subtotal in company currency lived in `currency_account`. They are now a
separate module so that the amounts and rates are computed in one place,
while `l10n_ve_seniat` keeps the fiscal rules of the documents.

Databases that already had `l10n_ve_seniat` or `currency_account` keep their
stored values: when this module is installed, it takes ownership of the
existing fields and views instead of creating new ones.
