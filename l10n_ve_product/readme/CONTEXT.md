Venezuelan invoices must state the tax rate that applies to each operation
(Art. 13, num. 9-11, Providencia Administrativa SNAT/2011/0071). A product
without a tax, or with two taxes for the same company, produces invoice lines
with a wrong or ambiguous rate.

These rules used to live in `l10n_ve_seniat`. Databases that already had
`l10n_ve_seniat` get this module installed when `l10n_ve_seniat` is upgraded,
so the rules keep applying.
