/** @odoo-module **/

import {TaxTotalsComponent} from "@account/components/tax_totals/tax_totals";
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
});

const TaxGroupComponent = TaxTotalsComponent.components.TaxGroupComponent;
if (TaxGroupComponent) {
    patch(TaxGroupComponent.prototype, {
        formatMonetaryCompany(value) {
            return formatCompanyAmount(this.props.totals?.company_currency_id, value);
        },
    });
}
