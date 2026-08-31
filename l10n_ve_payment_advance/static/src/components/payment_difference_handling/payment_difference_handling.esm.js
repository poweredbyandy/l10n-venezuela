import {RadioField, radioField} from "@web/views/fields/radio/radio_field";
import {registry} from "@web/core/registry";

export class PaymentDifferenceHandlingField extends RadioField {
    get items() {
        const items = super.items;
        if (this.props.record.data.show_advance_difference_handling) {
            return items;
        }
        return items.filter((item) => item[0] !== "advance");
    }
}

export const paymentDifferenceHandlingField = {
    ...radioField,
    component: PaymentDifferenceHandlingField,
};

registry
    .category("fields")
    .add("l10n_ve_payment_difference_handling", paymentDifferenceHandlingField);
