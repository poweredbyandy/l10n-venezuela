/** @odoo-module **/

import { TaxTotalsComponent } from "@account/components/tax_totals/tax_totals";
import { formatMonetary } from "@web/views/fields/formatters";
import { patch } from "@web/core/utils/patch";
import { usePopover } from "@web/core/popover/popover_hook";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

class L10nVeGlobalDiscountDetailsPopover extends Component {
    static template = "l10n_ve_seniat.GlobalDiscountDetailsPopover";
    static props = {
        lines: { type: Array },
        currencyId: { type: Number, optional: true },
        onRemove: { type: Function },
        onRemoveAll: { type: Function },
        close: { type: Function, optional: true },
    };

    get showRemoveAll() {
        return this.props.lines.length > 1;
    }

    formatAmount(amount) {
        return formatMonetary(amount, { currencyId: this.props.currencyId });
    }

    formatLineDetail(line) {
        if (line.discount_type === "percentage" && line.discount_percentage) {
            return `${(line.discount_percentage * 100).toFixed(2)}% (${this.formatAmount(line.amount)})`;
        }
        return this.formatAmount(line.amount);
    }

    async onRemoveClick(discountId) {
        await this.props.onRemove(discountId);
        this.props.close?.();
    }

    async onRemoveAllClick() {
        await this.props.onRemoveAll();
        this.props.close?.();
    }
}

const l10nVeGlobalDiscountTaxTotalsPatch = {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.discountPopover = usePopover(L10nVeGlobalDiscountDetailsPopover, {
            position: "left",
        });
    },

    get l10nVeDiscountTotals() {
        return this.totals || this.taxTotals || {};
    },

    get showGlobalDiscount() {
        return Boolean(this.l10nVeDiscountTotals.l10n_ve_show_global_discount);
    },

    get discountLines() {
        return this.l10nVeDiscountTotals.l10n_ve_global_discount_lines || [];
    },

    get displayInCompanyCurrency() {
        return Boolean(this.l10nVeDiscountTotals.display_in_company_currency);
    },

    formatGlobalDiscountAmount(amount, useCompanyCurrency = false) {
        if (typeof amount !== "number") {
            return "";
        }
        if (
            !useCompanyCurrency &&
            typeof this.formatMonetaryForeign === "function"
        ) {
            return this.formatMonetaryForeign(amount);
        }
        const totals = this.l10nVeDiscountTotals;
        const currencyId = useCompanyCurrency
            ? totals.company_currency_id
            : totals.currency_id;
        return formatMonetary(amount, { currencyId });
    },

    async removeGlobalDiscount(discountId) {
        await this.orm.call(
            this.props.record.resModel,
            "action_l10n_ve_remove_global_discount",
            [[this.props.record.resId], discountId]
        );
        await this.props.record.load();
    },

    async removeAllGlobalDiscounts() {
        await this.orm.call(
            this.props.record.resModel,
            "action_l10n_ve_remove_all_global_discounts",
            [[this.props.record.resId]]
        );
        await this.props.record.load();
    },

    onGlobalDiscountInfoClick(ev) {
        if (!this.discountLines.length) {
            return;
        }
        this.discountPopover.open(ev.currentTarget, {
            lines: this.discountLines,
            currencyId: this.l10nVeDiscountTotals.currency_id,
            onRemove: this.removeGlobalDiscount.bind(this),
            onRemoveAll: this.removeAllGlobalDiscounts.bind(this),
        });
    },
};

patch(TaxTotalsComponent.prototype, l10nVeGlobalDiscountTaxTotalsPatch);

const companyCurrencyField = registry
    .category("fields")
    .get("tax_totals_company_currency_widget", null);
if (companyCurrencyField?.component) {
    patch(companyCurrencyField.component.prototype, l10nVeGlobalDiscountTaxTotalsPatch);
}
