Adds the Point of Sale payment methods as terminal filter in the
terminal closings of `l10n_ve_payment_closing`.

The payments created by Point of Sale sessions keep their POS payment
method, so a closing can collect only the payments of one terminal even
when several terminals share the same bank journal.

It is installed automatically when both `l10n_ve_payment_closing` and
`point_of_sale` are installed.
