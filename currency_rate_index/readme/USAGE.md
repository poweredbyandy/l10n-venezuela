1. Keep native rates against VES for currencies that have a direct bolivar
   rate (USD/VES, USDT/VES, …).
2. For other currencies (CNY, JPY, …), load only the index rate against the
   index currency. The module creates or updates the native VES rate for the
   same date as: *foreign → index → VES*.
3. Manual native VES rates are never overwritten. Synced rates are refreshed
   when the index rate or the index currency VES rate changes.
4. Leave *Moneda índice* empty to disable the feature without uninstalling
   the module.
