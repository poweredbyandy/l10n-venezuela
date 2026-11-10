1. Install `l10n_ve_edi_stock` and `l10n_ve_edi_queue_job`. This module
   is installed automatically.
2. Send a dispatch guide from the EDI tab as usual.
3. The chatter records that the digital invoicing request was queued.
4. The worker sends the guide and updates the EDI state.
