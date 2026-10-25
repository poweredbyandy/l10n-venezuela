# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import models

from odoo.addons.account.models.chart_template import template

from .payroll_account_map import (
    PAYROLL_ACCOUNTS,
    RULE_ACCOUNT_MAP,
    VE_SENIAT_TEMPLATE_CODES,
)

_logger = logging.getLogger(__name__)


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _l10n_ve_payroll_accounts_template_data(self):
        """Accounts to inject on empty/basic SENIAT charts (full chart has CSV)."""
        return {
            f"l10n_ve_payroll_account.{xmlid}": dict(vals)
            for xmlid, vals in PAYROLL_ACCOUNTS.items()
        }

    @template("ve_seniat_empty", "account.account")
    def _get_ve_seniat_empty_payroll_account(self):
        return self._l10n_ve_payroll_accounts_template_data()

    @template("ve_seniat_basic", "account.account")
    def _get_ve_seniat_basic_payroll_account(self):
        return self._l10n_ve_payroll_accounts_template_data()

    def _post_load_data(self, template_code, company, template_data):
        res = super()._post_load_data(template_code, company, template_data)
        company = company or self.env.company
        if template_code in VE_SENIAT_TEMPLATE_CODES:
            self._l10n_ve_payroll_map_salary_rule_accounts(company)
            self._l10n_ve_payroll_configure_loan_account(company)
        return res

    def _l10n_ve_payroll_configure_companies(self, companies=None):
        """Ensure payroll accounts exist and salary rules are mapped (install/upgrade)."""
        companies = companies or self.env["res.company"].search([])
        for company in companies:
            if (
                not company.account_fiscal_country_id
                or company.account_fiscal_country_id.code != "VE"
            ):
                continue
            if not company.chart_template:
                continue
            self.with_company(company)._l10n_ve_payroll_ensure_accounts(company)
            self.with_company(company)._l10n_ve_payroll_map_salary_rule_accounts(
                company
            )
            self.with_company(company)._l10n_ve_payroll_configure_loan_account(
                company
            )

    def _l10n_ve_payroll_ensure_accounts(self, company):
        """Create missing SENIAT payroll accounts for the company chart."""
        company = company or self.env.company
        chart = self.with_company(company)
        template_code = company.chart_template
        to_create = {}
        for xmlid, vals in PAYROLL_ACCOUNTS.items():
            account = chart._l10n_ve_payroll_find_account(company, xmlid, vals["code"])
            if account:
                continue
            if template_code in ("ve_seniat_empty", "ve_seniat_basic"):
                to_create[f"l10n_ve_payroll_account.{xmlid}"] = dict(vals)
            else:
                # Full SENIAT: prefer short xmlid used by chart CSV.
                to_create[xmlid] = dict(vals)
        if not to_create:
            return
        _logger.info(
            "Creating %s Venezuelan payroll accounts for company %s",
            len(to_create),
            company.display_name,
        )
        chart._load_data({"account.account": to_create}, ignore_duplicates=True)

    def _l10n_ve_payroll_find_account(self, company, xmlid_suffix, code):
        chart = self.with_company(company)
        account = chart.ref(xmlid_suffix, raise_if_not_found=False)
        if account:
            return account
        account = self.env.ref(
            f"l10n_ve_payroll_account.{xmlid_suffix}", raise_if_not_found=False
        )
        if account and company in account.company_ids:
            return account
        account = self.env.ref(
            f"l10n_ve_seniat.{xmlid_suffix}", raise_if_not_found=False
        )
        if account and company in account.company_ids:
            return account
        Account = self.env["account.account"].with_company(company)
        return Account.search(
            [("code", "=", code), ("company_ids", "in", company.id)],
            limit=1,
        )

    def _l10n_ve_payroll_configure_loan_account(self, company):
        """Set company loan receivable from SENIAT 1106002 when empty."""
        company = company or self.env.company
        if company.loan_receivable_account_id:
            return
        account = self._l10n_ve_payroll_find_account(
            company,
            "account_account_1106002",
            PAYROLL_ACCOUNTS["account_account_1106002"]["code"],
        )
        if account:
            company.loan_receivable_account_id = account

    def _l10n_ve_payroll_map_salary_rule_accounts(self, company):
        """Set account_debit/credit on salary rules from SENIAT CoA mapping."""
        company = company or self.env.company
        chart = self.with_company(company)
        Rule = self.env["hr.salary.rule"].sudo()
        rules = Rule.search([("code", "in", list(RULE_ACCOUNT_MAP))])
        updated = 0
        for rule in rules:
            debit_xmlid, credit_xmlid = RULE_ACCOUNT_MAP[rule.code]
            debit = chart._l10n_ve_payroll_find_account(
                company, debit_xmlid, PAYROLL_ACCOUNTS[debit_xmlid]["code"]
            )
            credit = chart._l10n_ve_payroll_find_account(
                company, credit_xmlid, PAYROLL_ACCOUNTS[credit_xmlid]["code"]
            )
            vals = {}
            if debit and rule.account_debit != debit:
                vals["account_debit"] = debit.id
            if credit and rule.account_credit != credit:
                vals["account_credit"] = credit.id
            if debit_xmlid in PAYROLL_ACCOUNTS:
                vals["l10n_ve_account_code_debit"] = PAYROLL_ACCOUNTS[debit_xmlid][
                    "code"
                ]
            if credit_xmlid in PAYROLL_ACCOUNTS:
                vals["l10n_ve_account_code_credit"] = PAYROLL_ACCOUNTS[credit_xmlid][
                    "code"
                ]
            if vals:
                rule.write(vals)
                updated += 1
        _logger.info(
            "Mapped accounts on %s salary rules for company %s",
            updated,
            company.display_name,
        )
