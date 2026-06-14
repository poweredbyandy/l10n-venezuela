DELETE FROM ir_config_parameter
WHERE key IN (
    'l10n_ve_edi_tfhka.username',
    'l10n_ve_edi_tfhka.password',
    'l10n_ve_edi_tfhka.production_url'
);
UPDATE ir_config_parameter
SET value = 'https://demoemisionv2.thefactoryhka.com.ve'
WHERE key = 'l10n_ve_edi_tfhka.base_url';
UPDATE ir_config_parameter
SET value = 'test'
WHERE key = 'l10n_ve_edi_tfhka.api_environment';
