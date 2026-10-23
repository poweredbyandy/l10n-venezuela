import {TaxTotalsComponent} from "@account/components/tax_totals/tax_totals";
import {formatMonetary} from "@web/views/fields/formatters";
import {formatFloat} from "@web/core/utils/numbers";
import {parseFloat} from "@web/views/fields/parsers";
import {patch} from "@web/core/utils/patch";
import {Component, onPatched, useRef, useState} from "@odoo/owl";

export class EditableMonetary extends Component {
    static template = "l10n_ve_tax_totals_manual.EditableMonetary";
    static props = {
        value: Number,
        currencyId: {type: Number, optional: true},
        editable: {type: Boolean, optional: true},
        readonly: {type: Boolean, optional: true},
        digits: {type: Array, optional: true},
        style: {type: String, optional: true},
        name: {type: String, optional: true},
        onChange: Function,
    };

    setup() {
        this.input = useRef("input");
        this.state = useState({editing: false, done: false, seeded: false});
        onPatched(() => {
            if (this.state.editing && this.input.el && !this.state.seeded) {
                const digits = this.props.digits || [16, 2];
                this.input.el.value = formatFloat(this.props.value || 0, {digits});
                this.input.el.focus();
                this.input.el.select();
                this.state.seeded = true;
            }
        });
    }

    get formatted() {
        if (!this.props.currencyId && this.props.currencyId !== 0) {
            return "";
        }
        return formatMonetary(this.props.value || 0, {
            currencyId: this.props.currencyId,
        });
    }

    startEdit(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.state.done = false;
        this.state.seeded = false;
        this.state.editing = true;
    }

    commit() {
        if (this.state.done || !this.input.el) {
            return;
        }
        this.state.done = true;
        const previous = this.props.value || 0;
        let newValue;
        try {
            newValue = parseFloat(this.input.el.value);
        } catch {
            this.state.editing = false;
            this.state.done = false;
            return;
        }
        this.state.editing = false;
        if (newValue === previous) {
            this.state.done = false;
            return;
        }
        this.props.onChange(newValue);
    }
}

patch(TaxTotalsComponent.prototype, {
    _paintManualValue(totals, kind, newValue, subtotalName, taxGroupId) {
        const subtotals = totals.subtotals || [];
        const subtotal =
            subtotals.find((item) => item.name === subtotalName) || subtotals[0];
        if (kind === "subtotal_company" && subtotal) {
            subtotal.base_amount = newValue;
        } else if (kind === "subtotal_currency" && subtotal) {
            subtotal.base_amount_currency = newValue;
        } else if (kind === "gross_company") {
            totals.l10n_ve_subtotal_gross = newValue;
        } else if (kind === "gross_currency") {
            totals.l10n_ve_subtotal_gross_currency = newValue;
        } else if (kind === "total_company") {
            totals.total_amount = newValue;
        } else if (kind === "total_currency") {
            totals.total_amount_currency = newValue;
        } else if (kind === "discount_company") {
            totals.l10n_ve_global_discount_amount = Math.abs(newValue);
        } else if (kind === "discount_currency") {
            totals.l10n_ve_global_discount_amount_currency = Math.abs(newValue);
        } else if (kind === "tax_company") {
            for (const item of subtotals) {
                const group = (item.tax_groups || []).find(
                    (taxGroup) => taxGroup.id === taxGroupId
                );
                if (group) {
                    group.tax_amount = newValue;
                }
            }
        }
    },

    onManualAmount(kind, newValue, subtotalName, taxGroupId) {
        const totals = JSON.parse(JSON.stringify(this.totals || {}));
        this._paintManualValue(totals, kind, newValue, subtotalName, taxGroupId);
        totals.manual_edit = {
            kind,
            new_value: newValue,
            subtotal_name: subtotalName || false,
            tax_group_id: taxGroupId || false,
        };
        this.totals = totals;
        this.props.record.update({[this.props.name]: totals});
    },

    onTaxGroupManualEdit(edit) {
        this.onManualAmount(edit.kind, edit.newValue, false, edit.taxGroupId);
    },
});

TaxTotalsComponent.components = {
    ...TaxTotalsComponent.components,
    EditableMonetary,
};

const TaxGroupComponent = TaxTotalsComponent.components.TaxGroupComponent;
if (TaxGroupComponent) {
    TaxGroupComponent.components = {
        ...(TaxGroupComponent.components || {}),
        EditableMonetary,
    };
    TaxGroupComponent.props = {
        ...TaxGroupComponent.props,
        onManualEdit: {type: Function, optional: true},
    };
    patch(TaxGroupComponent.prototype, {
        onCompanyTaxChange(newValue) {
            this.props.onManualEdit?.({
                kind: "tax_company",
                newValue,
                taxGroupId: this.props.taxGroup.id,
            });
        },
    });
}
