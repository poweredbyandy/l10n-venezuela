import {accountTaxHelpers} from "@account/helpers/account_tax";
import {patch} from "@web/core/utils/patch";
import {roundPrecision} from "@web/core/utils/numbers";

/**
 * Mirror of account.tax._l10n_ve_align_company_amounts_from_rounded_foreign.
 * Keep company-currency amounts aligned with rounded foreign monetary amounts.
 */
patch(accountTaxHelpers, {
    add_tax_details_in_base_line(base_line, company, options = {}) {
        super.add_tax_details_in_base_line(base_line, company, options);
        this._l10n_ve_align_company_amounts_from_rounded_foreign(base_line, company);
    },

    _l10n_ve_align_company_amounts_from_rounded_foreign(base_line, company) {
        const currency = base_line.currency_id;
        const companyCurrency = company.currency_id;
        const rate = base_line.rate || 0.0;
        const taxDetails = base_line.tax_details;
        if (
            !taxDetails ||
            !currency ||
            !companyCurrency ||
            !rate ||
            currency === companyCurrency ||
            currency.id === companyCurrency.id
        ) {
            return;
        }
        const currencyPd = currency.rounding;
        const companyPd = companyCurrency.rounding;
        const toCompany = (amountCurrency) =>
            roundPrecision(roundPrecision(amountCurrency, currencyPd) / rate, companyPd);

        taxDetails.raw_total_excluded = toCompany(
            taxDetails.raw_total_excluded_currency
        );
        taxDetails.raw_total_included = toCompany(
            taxDetails.raw_total_included_currency
        );
        for (const taxData of taxDetails.taxes_data || []) {
            taxData.raw_tax_amount = toCompany(taxData.raw_tax_amount_currency);
            taxData.raw_base_amount = toCompany(taxData.raw_base_amount_currency);
        }
    },
});
