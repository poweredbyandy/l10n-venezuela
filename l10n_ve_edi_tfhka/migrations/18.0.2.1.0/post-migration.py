def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        INSERT INTO ir_config_parameter (
            key, value, create_uid, write_uid, create_date, write_date
        )
        SELECT
            CASE
                WHEN env.value = 'production'
                    THEN 'l10n_ve_edi_tfhka.username_production'
                ELSE 'l10n_ve_edi_tfhka.username_test'
            END,
            cred.value,
            1,
            1,
            NOW() AT TIME ZONE 'UTC',
            NOW() AT TIME ZONE 'UTC'
        FROM ir_config_parameter cred
        LEFT JOIN ir_config_parameter env
            ON env.key = 'l10n_ve_edi_tfhka.api_environment'
        WHERE cred.key = 'l10n_ve_edi_tfhka.username'
          AND COALESCE(cred.value, '') != ''
          AND NOT EXISTS (
              SELECT 1
              FROM ir_config_parameter existing
              WHERE existing.key = CASE
                  WHEN env.value = 'production'
                      THEN 'l10n_ve_edi_tfhka.username_production'
                  ELSE 'l10n_ve_edi_tfhka.username_test'
              END
          )
        """
    )
    cr.execute(
        """
        INSERT INTO ir_config_parameter (
            key, value, create_uid, write_uid, create_date, write_date
        )
        SELECT
            CASE
                WHEN env.value = 'production'
                    THEN 'l10n_ve_edi_tfhka.password_production'
                ELSE 'l10n_ve_edi_tfhka.password_test'
            END,
            cred.value,
            1,
            1,
            NOW() AT TIME ZONE 'UTC',
            NOW() AT TIME ZONE 'UTC'
        FROM ir_config_parameter cred
        LEFT JOIN ir_config_parameter env
            ON env.key = 'l10n_ve_edi_tfhka.api_environment'
        WHERE cred.key = 'l10n_ve_edi_tfhka.password'
          AND COALESCE(cred.value, '') != ''
          AND NOT EXISTS (
              SELECT 1
              FROM ir_config_parameter existing
              WHERE existing.key = CASE
                  WHEN env.value = 'production'
                      THEN 'l10n_ve_edi_tfhka.password_production'
                  ELSE 'l10n_ve_edi_tfhka.password_test'
              END
          )
        """
    )
    cr.execute(
        """
        INSERT INTO ir_config_parameter (
            key, value, create_uid, write_uid, create_date, write_date
        )
        SELECT
            CASE
                WHEN env.value = 'production'
                    THEN 'l10n_ve_edi_tfhka.production_url'
                ELSE 'l10n_ve_edi_tfhka.test_url'
            END,
            url.value,
            1,
            1,
            NOW() AT TIME ZONE 'UTC',
            NOW() AT TIME ZONE 'UTC'
        FROM ir_config_parameter url
        LEFT JOIN ir_config_parameter env
            ON env.key = 'l10n_ve_edi_tfhka.api_environment'
        WHERE url.key = 'l10n_ve_edi_tfhka.base_url'
          AND COALESCE(url.value, '') != ''
          AND NOT EXISTS (
              SELECT 1
              FROM ir_config_parameter existing
              WHERE existing.key = CASE
                  WHEN env.value = 'production'
                      THEN 'l10n_ve_edi_tfhka.production_url'
                  ELSE 'l10n_ve_edi_tfhka.test_url'
              END
          )
        """
    )
