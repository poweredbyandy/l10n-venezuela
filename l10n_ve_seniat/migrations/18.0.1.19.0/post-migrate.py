import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _template_exempt_group(env, company):
    group = env.ref(f"account.{company.id}_tax_group_iva_0", raise_if_not_found=False)
    if group and group.l10n_ve_exclude_from_reports:
        return group
    return env["account.tax.group"]


def _exempt_group_to_configure(env, company, ve_country):
    TaxGroup = env["account.tax.group"]
    domain = [("company_id", "=", company.id), ("country_id", "=", ve_country.id)]
    if TaxGroup.search_count(domain + [("l10n_ve_aliquot_type", "=", "exempt")]):
        return TaxGroup
    group = _template_exempt_group(env, company)
    if group:
        return group
    candidates = TaxGroup.search(domain + [("l10n_ve_exclude_from_reports", "=", True)])
    if len(candidates) == 1:
        return candidates
    if candidates:
        _logger.warning(
            "Company %s has %s tax groups excluded from reports; set the exempt "
            "aliquot on the right one manually",
            company.name,
            len(candidates),
        )
    return TaxGroup


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    ve_country = env.ref("base.ve", raise_if_not_found=False)
    if not ve_country:
        return
    companies = env["res.company"].search(
        [("account_fiscal_country_id", "=", ve_country.id)]
    )
    for company in companies:
        group = _exempt_group_to_configure(env, company, ve_country)
        if not group:
            continue
        group.write(
            {"l10n_ve_exclude_from_reports": False, "l10n_ve_aliquot_type": "exempt"}
        )
        _logger.info(
            "Set exempt aliquot on tax group %s of %s", group.name, company.name
        )
