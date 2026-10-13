import logging

_logger = logging.getLogger(__name__)

_XMLIDS = ("partner_demo_company_ve", "demo_company_ve")


def pre_init_hook(env):
    env.cr.execute(
        """
        UPDATE ir_model_data imd
           SET module = 'l10n_ve_coa'
         WHERE imd.module = 'l10n_ve_seniat'
           AND imd.name IN %s
           AND NOT EXISTS (
               SELECT 1
                 FROM ir_model_data dup
                WHERE dup.module = 'l10n_ve_coa'
                  AND dup.name = imd.name
           )
        """,
        (_XMLIDS,),
    )
    if env.cr.rowcount:
        _logger.info(
            "Moved %s demo xmlids from l10n_ve_seniat to l10n_ve_coa",
            env.cr.rowcount,
        )
