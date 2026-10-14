Groups the payments of a card terminal (punto de venta) for one day into
a single journal item, ready to be matched with the single bank
transaction deposited by the bank.

A terminal closing collects every pending payment of a bank journal and
date, optionally filtered by payment method. When posted, it creates one
journal entry that:

- reconciles the outstanding line of each payment, keeping the link
  between the closing and every payment;
- leaves one open line on the outstanding account for the closing total,
  netting refunds even when they use another outstanding account.

That open line is the one to match with the bank statement line.
