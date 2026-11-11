import {TaxTotalsComponent} from "@account/components/tax_totals/tax_totals";
import {_t} from "@web/core/l10n/translation";
import {formatMonetary} from "@web/views/fields/formatters";
import {patch} from "@web/core/utils/patch";

function formatCompanyAmount(currencyId, value) {
    if (value === undefined || value === null) {
        return "";
    }
    return formatMonetary(value, {currencyId});
}

patch(TaxTotalsComponent.prototype, {
    formatMonetaryCompany(value) {
        return formatCompanyAmount(this.totals?.company_currency_id, value);
    },

    currencyCode(useCompanyCurrency) {
        if (!this.totals) {
            return "";
        }
        return useCompanyCurrency
            ? this.totals.company_currency_name || ""
            : this.totals.currency_name || "";
    },

    responsiveLabel(title, useCompanyCurrency) {
        const code = this.currencyCode(useCompanyCurrency);
        return code ? `${title} ${code}` : title;
    },

    responsiveTotalLabel(useCompanyCurrency) {
        return this.responsiveLabel(_t("Total"), useCompanyCurrency);
    },

    responsiveRoundingLabel(useCompanyCurrency) {
        return this.responsiveLabel(_t("Rounding"), useCompanyCurrency);
    },
});

const TaxGroupComponent = TaxTotalsComponent.components.TaxGroupComponent;
if (TaxGroupComponent) {
    patch(TaxGroupComponent.prototype, {
        formatMonetaryCompany(value) {
            return formatCompanyAmount(this.props.totals?.company_currency_id, value);
        },
    });
}
