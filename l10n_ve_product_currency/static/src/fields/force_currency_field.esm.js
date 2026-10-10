import {registry} from "@web/core/registry";
import {
    Many2OneField,
    many2OneField,
} from "@web/views/fields/many2one/many2one_field";

export class L10nVeForceCurrencyField extends Many2OneField {
    static props = {
        ...Many2OneField.props,
        placeholderField: {type: String, optional: true},
    };
    static defaultProps = {
        ...Many2OneField.defaultProps,
    };

    get fallbackCurrencyName() {
        const fieldName = this.props.placeholderField;
        const fallback = fieldName && this.props.record.data[fieldName];
        if (typeof fallback === "string") {
            return fallback;
        }
        if (Array.isArray(fallback) && fallback[1]) {
            return fallback[1].split("\n")[0];
        }
        return "";
    }

    get displayName() {
        const name = super.displayName;
        if (name || !this.props.readonly) {
            return name;
        }
        return this.fallbackCurrencyName;
    }

    get Many2XAutocompleteProps() {
        const props = super.Many2XAutocompleteProps;
        if (!this.value && this.fallbackCurrencyName) {
            props.placeholder = this.fallbackCurrencyName;
        }
        return props;
    }
}

export const l10nVeForceCurrencyField = {
    ...many2OneField,
    component: L10nVeForceCurrencyField,
    fieldDependencies: ({options}) => {
        const name = options.placeholder_field;
        if (!name) {
            return [];
        }
        return [{name, type: "many2one", relation: "res.currency"}];
    },
    extractProps(fieldInfo, dynamicInfo) {
        const props = many2OneField.extractProps(fieldInfo, dynamicInfo);
        props.placeholderField = fieldInfo.options.placeholder_field;
        return props;
    },
};

registry.category("fields").add("l10n_ve_force_currency", l10nVeForceCurrencyField);
