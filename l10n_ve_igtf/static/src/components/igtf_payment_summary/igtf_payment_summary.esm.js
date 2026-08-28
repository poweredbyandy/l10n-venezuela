import {Component} from "@odoo/owl";
import {_t} from "@web/core/l10n/translation";
import {formatFloat} from "@web/core/utils/numbers";
import {formatMonetary} from "@web/views/fields/formatters";
import {registry} from "@web/core/registry";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

export class L10nVeIgtfPaymentSummary extends Component {
    static props = {...standardFieldProps};
    static template = "l10n_ve_igtf.IgtfPaymentSummary";

    get recordData() {
        return this.props.record.data;
    }

    get paymentCurrencyId() {
        return this._getCurrencyId(this.recordData.currency_id);
    }

    get companyCurrencyId() {
        return this._getCurrencyId(this.recordData.company_currency_id);
    }

    get showPaymentCurrency() {
        return (
            this.paymentCurrencyId &&
            this.companyCurrencyId &&
            this.paymentCurrencyId !== this.companyCurrencyId
        );
    }

    get baseCompany() {
        return this.recordData.l10n_ve_base_amount_company_currency || 0;
    }

    get igtfPayment() {
        return this.recordData.l10n_ve_igtf_amount_currency || 0;
    }

    get igtfCompany() {
        return this.recordData.l10n_ve_igtf_amount_company_currency || 0;
    }

    get baseLabel() {
        return _t("Base");
    }

    get formattedRate() {
        const rate = this.recordData.l10n_ve_igtf_exchange_rate_inverse;
        if (!rate) {
            return "";
        }
        return formatFloat(rate, {digits: [12, 6]});
    }

    formatAmount(amount, currencyId) {
        if (amount === undefined || amount === null || !currencyId) {
            return "";
        }
        return formatMonetary(amount, {currencyId});
    }

    _getCurrencyId(value) {
        if (!value) {
            return null;
        }
        if (typeof value === "number") {
            return value;
        }
        if (Array.isArray(value)) {
            return value[0];
        }
        return value.id || null;
    }
}

registry.category("fields").add("l10n_ve_igtf_payment_summary", {
    component: L10nVeIgtfPaymentSummary,
    supportedTypes: ["monetary"],
});
