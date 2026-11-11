import {Component, onWillRender, toRaw} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
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

    currencyCode(useCompanyCurrency = false) {
        if (!this.taxTotals) {
            return "";
        }
        return useCompanyCurrency
            ? this.taxTotals.company_currency_name || ""
            : this.taxTotals.currency_name || "";
    }

    responsiveLabel(title, useCompanyCurrency = false) {
        const code = this.currencyCode(useCompanyCurrency);
        return code ? `${title} ${code}` : title;
    }

    responsiveBaseLabel(useCompanyCurrency = false) {
        return this.responsiveLabel(_t("Importe base"), useCompanyCurrency);
    }

    responsiveTotalLabel(useCompanyCurrency = false) {
        return this.responsiveLabel(_t("Total"), useCompanyCurrency);
    }

    responsiveRoundingLabel(useCompanyCurrency = false) {
        return this.responsiveLabel(_t("Rounding"), useCompanyCurrency);
    }

    responsiveIgtfTotalLabel(useCompanyCurrency = false) {
        return this.responsiveLabel(_t("Total con IGTF"), useCompanyCurrency);
    }

    taxGroupText(taxGroup, useCompanyCurrency = false) {
        const base = useCompanyCurrency
            ? (taxGroup.display_base_amount ?? taxGroup.base_amount ?? 0)
            : (taxGroup.display_base_amount_currency ??
              taxGroup.base_amount_currency ??
              0);
        const tax = useCompanyCurrency
            ? taxGroup.tax_amount || 0
            : taxGroup.tax_amount_currency || 0;
        return `(${this.formatAmount(base, useCompanyCurrency)}) ${this.formatAmount(tax, useCompanyCurrency)}`;
    }
}

registry.category("fields").add("l10n_ve_igtf_tax_totals", {
    component: L10nVeIgtfTaxTotals,
});
