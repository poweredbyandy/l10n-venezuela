DELETE FROM ir_config_parameter
WHERE key IN (
    'l10n_ve_edi_tfhka.username',
    'l10n_ve_edi_tfhka.password',
    'l10n_ve_edi_tfhka.username_production',
    'l10n_ve_edi_tfhka.password_production',
    'l10n_ve_edi_tfhka.production_url'
);
UPDATE ir_config_parameter
SET value = COALESCE(
    (
        SELECT value
        FROM ir_config_parameter
        WHERE key = 'l10n_ve_edi_tfhka.test_url'
          AND COALESCE(value, '') != ''
    ),
    'https://demoemisionv2.thefactoryhka.com.ve'
)
WHERE key = 'l10n_ve_edi_tfhka.base_url';
UPDATE ir_config_parameter
SET value = 'test'
WHERE key = 'l10n_ve_edi_tfhka.api_environment';
INSERT INTO ir_config_parameter (
    key, value, create_uid, write_uid, create_date, write_date
)
SELECT
    'l10n_ve_edi_tfhka.api_environment',
    'test',
    1,
    1,
    NOW() AT TIME ZONE 'UTC',
    NOW() AT TIME ZONE 'UTC'
WHERE NOT EXISTS (
    SELECT 1
    FROM ir_config_parameter
    WHERE key = 'l10n_ve_edi_tfhka.api_environment'
);
