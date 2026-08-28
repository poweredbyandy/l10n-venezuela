import {Component, onWillRender, toRaw} from "@odoo/owl";
import {formatMonetary} from "@web/views/fields/formatters";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export class L10nVeIgtfTaxTotals extends Component {
    static props = {...standardFieldProps};
    static template = "l10n_ve_igtf.TaxTotalsField";

    setup() {
        this.taxTotals = null;
        this.currencyId = null;
        this.companyCurrencyId = null;
        this.formatData(this.props);
        onWillRender(() => this.formatData(this.props));
    }

    formatData(props) {
        const raw = toRaw(props.record.data.tax_totals);
        if (!raw) {
            this.taxTotals = null;
            return;
        }
        this.taxTotals = JSON.parse(JSON.stringify(raw));
        this.currencyId = this.taxTotals.currency_id;
        this.companyCurrencyId = this.taxTotals.company_currency_id;
    }

    get hasIgtfTotal() {
        return Boolean(
            this.taxTotals &&
                Object.prototype.hasOwnProperty.call(
                    this.taxTotals,
                    "l10n_ve_igtf_total_without_igtf_currency"
                )
        );
    }

    formatAmount(amount, useCompanyCurrency = false) {
        if (amount === undefined || amount === null) {
            return "";
        }
        const currencyId = useCompanyCurrency
            ? this.companyCurrencyId
            : this.currencyId;
        return formatMonetary(amount, {currencyId});
    }
}

registry.category("fields").add("l10n_ve_igtf_tax_totals", {
    component: L10nVeIgtfTaxTotals,
});
