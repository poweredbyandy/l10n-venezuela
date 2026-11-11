1. Install `l10n_ve_edi_tfhka` after `l10n_ve_edi`. To send dispatch
   guides, also install `l10n_ve_edi_stock_tfhka`.
2. In **Settings**, choose Pruebas or Producción and fill the URL,
   username and password of each environment. The connection test uses
   the selected environment. A neutralized database stays on Pruebas
   and drops the production credentials.
3. On each sales or withholding journal used for digital emission,
   choose provider **The Factory HKA** and set serie, branch and
   environment digit so they match the numbering range in the TFHKA
   portal.
4. Click **Numeración TFHKA** on the journal to check that TFHKA has an
   available numbering range for each document type you emit.
5. For customers outside Venezuela, set the country, the tax ID and the
   field **Tipo de identificación extranjera (TFHKA)** (for example RUT
   or NIT) on the contact.
