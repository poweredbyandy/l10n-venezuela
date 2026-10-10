In Venezuela the company currency is usually VES, while commercial
operations often compare foreign currencies such as USD, USDT or JPY.

Native Odoo rates always go through VES, so USD ↔ USDT inherits the
spread between their bolivar rates. This module lets companies configure
an index currency and load direct rates against it, so those cross
conversions stay independent from the bolivar rates used for accounting.
