Requires `l10n_ve_escp` and its Python dependency `pyscape` (EscaPy) for the PDF preview. See that module's installation notes.

Upgrading from 18.0.2.x: the former per-journal layouts (`l10n.ve.invoice.escp.layout`) are replaced by ESC/P reports. Journals on continuous paper are pointed to the shipped invoice report; recreate any custom positions as a duplicated report.
