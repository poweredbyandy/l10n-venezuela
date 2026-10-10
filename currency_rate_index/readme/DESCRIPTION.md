Adds direct exchange rates against a configurable index currency.

When converting between two foreign currencies (neither is the company
currency), Odoo uses the index rates if both currencies have one for the
requested date. Otherwise it keeps the native conversion through the
company currency (VES).

When a foreign currency has an index rate and no native rate against VES,
conversions to or from VES go through the index currency:

CNY → USD → VES

Example with company currency VES and index currency USD:

- Native rates: 1 USD = 876 Bs, 1 USDT = 1000 Bs
- Index rates: 1 USDT = 1 USD, 1 CNY = 0.14 USD
- Converting 100 USDT to USD returns 100 USD (index), not 114.16 USD (via VES)
- Converting 100 CNY to VES returns 100 × 0.14 × 876 Bs (via USD), not 100 Bs
- USDT → VES stays native (1000) because USDT has a native VES rate

Each index rate stores both directions: index per unit and unit per index
(for example USD per CNY and CNY per USD).
