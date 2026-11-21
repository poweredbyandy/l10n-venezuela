# Part of Odoo. See LICENSE file for full copyright and licensing details.

"""Backfill the person classification columns for pre-existing partners.

New columns added by 18.0.1.26.0:

* ``l10n_ve_tax_residence`` — plain stored selection. Backfilled with the
  same derivation used at create time (see ``res_partner.py`` and
  docs/adr/0001): RIF kind ``E`` -> resident, kind ``P`` -> non_resident,
  country VE (company country as fallback when unset) -> resident, else
  non_resident. The kind must be a full letter+digits RIF, mirroring
  ``_l10n_ve_rif_kind_from_vat``.
* ``l10n_ve_person_nature`` / ``l10n_ve_person_type`` — stored computes.
  They are also backfilled here with SQL rules identical to the Python
  ones, so the columns are correct even when the ORM does not schedule a
  full recomputation during the upgrade.

The rules in this file MUST stay in sync with
``l10n_ve_seniat/models/res_partner.py``.
"""

import logging

_logger = logging.getLogger(__name__)

# UPPER(cleaned vat) of the partner, computed inline in the UPDATEs.
_CLEAN_VAT = (
    "UPPER(REGEXP_REPLACE(COALESCE(partner.vat, ''), '[^A-Za-z0-9]', '', 'g'))"
)
_IS_RIF = f"{_CLEAN_VAT} ~ '^[VEJCPG][0-9]{{6,10}}$'"
_KIND = f"UPPER(SUBSTRING({_CLEAN_VAT} FROM 1 FOR 1))"


def _table_exists(cr, table):
    cr.execute(
        "SELECT EXISTS (SELECT FROM information_schema.tables "
        "WHERE table_name = %s)",
        [table],
    )
    return bool(cr.fetchone()[0])


_COMPANY_COUNTRY = """
    (SELECT company_country.code
       FROM res_company company
       JOIN res_partner company_partner
         ON company_partner.id = company.partner_id
       LEFT JOIN res_country company_country
         ON company_country.id = company_partner.country_id
      WHERE company.id = 1)
"""


def _residence_with_country_sql():
    return f"""
        UPDATE res_partner partner
           SET l10n_ve_tax_residence = CASE
               WHEN {_CLEAN_VAT} ~ '^[E][0-9]{{6,10}}$' THEN 'resident'
               WHEN {_CLEAN_VAT} ~ '^[P][0-9]{{6,10}}$' THEN 'non_resident'
               WHEN COALESCE(country.code, {_COMPANY_COUNTRY}, '') = 'VE'
                   THEN 'resident'
               ELSE 'non_resident'
           END
          FROM res_country country
         WHERE partner.l10n_ve_tax_residence IS NULL
           AND partner.country_id = country.id
    """


def _residence_without_country_sql():
    return f"""
        UPDATE res_partner partner
           SET l10n_ve_tax_residence = CASE
               WHEN {_CLEAN_VAT} ~ '^[E][0-9]{{6,10}}$' THEN 'resident'
               WHEN {_CLEAN_VAT} ~ '^[P][0-9]{{6,10}}$' THEN 'non_resident'
               WHEN COALESCE({_COMPANY_COUNTRY}, '') = 'VE' THEN 'resident'
               ELSE 'non_resident'
           END
         WHERE partner.l10n_ve_tax_residence IS NULL
           AND partner.country_id IS NULL
    """


def _nature_sql():
    return """
        UPDATE res_partner partner
           SET l10n_ve_person_nature = CASE
               WHEN {is_rif} AND {kind} IN ('V', 'E', 'P') THEN 'natural'
               WHEN {is_rif} AND {kind} IN ('J', 'G', 'C') THEN 'legal'
               WHEN partner.is_company THEN 'legal'
               ELSE 'natural'
           END
    """.format(is_rif=_IS_RIF, kind=_KIND)


def _person_type_sql():
    return """
        UPDATE res_partner partner
           SET l10n_ve_person_type = CASE
               WHEN partner.l10n_ve_person_nature = 'legal'
                    AND partner.l10n_ve_tax_residence = 'resident'
                   THEN 'pj_domiciled'
               WHEN partner.l10n_ve_person_nature = 'legal'
                   THEN 'pj_non_domiciled'
               WHEN partner.l10n_ve_tax_residence = 'resident'
                   THEN 'pn_resident'
               ELSE 'pn_non_resident'
           END
    """


def migrate(cr, version):
    if not _table_exists(cr, "res_partner"):
        return
    if not _table_exists(cr, "res_country"):
        return

    cr.execute("SELECT count(*) FROM res_partner")
    total = cr.fetchone()[0]

    cr.execute(_residence_with_country_sql())
    with_country = cr.rowcount
    cr.execute(_residence_without_country_sql())
    without_country = cr.rowcount
    cr.execute(_nature_sql())
    nature_rows = cr.rowcount
    cr.execute(_person_type_sql())
    type_rows = cr.rowcount

    cr.execute(
        """
        SELECT l10n_ve_person_nature, l10n_ve_tax_residence,
               l10n_ve_person_type, count(*)
          FROM res_partner
         GROUP BY 1, 2, 3
         ORDER BY 4 DESC
        """
    )
    distribution = cr.fetchall()
    _logger.info(
        "l10n_ve_seniat 18.0.1.26.0 backfill de clasificación de persona: "
        "total=%s residencia_con_pais=%s residencia_sin_pais=%s "
        "naturaleza=%s tipo=%s distribución=%s",
        total,
        with_country,
        without_country,
        nature_rows,
        type_rows,
        distribution,
    )
